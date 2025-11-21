"""Agent orchestrator - coordinates tool execution with LangChain"""
from typing import Any, Dict, List, Sequence

from ..services.database import fetch_recent_emails, get_weekly_metrics, store_email_memory
from ..tools.auto_reply import AutoReplyTool
from ..tools.content_analysis import ContentAnalysisTool
from ..tools.filtering import FilteringTool
from ..tools.newsletter import NewsletterTool
from .chain import AgentChain

# Agent capabilities description
CAPABILITIES_TIP = (
    "Агент умеет: фильтровать письма, управлять рассылками, находить задачи и дедлайны, "
    "готовить автоответы и недельные отчёты."
)


class AgentOrchestrator:
    """Orchestrates AI agent tools to analyze emails"""
    
    def __init__(self) -> None:
        """Initialize orchestrator with all available tools and LangChain chain"""
        # Initialize LangChain agent chain
        self.chain = AgentChain()
        
        # Initialize tools with shared LLM instance for efficiency
        shared_llm = self.chain.llm
        self.filter_tool = FilteringTool(llm=shared_llm)
        self.newsletter_tool = NewsletterTool(llm=shared_llm)
        self.content_tool = ContentAnalysisTool(llm=shared_llm)
        self.auto_reply_tool = AutoReplyTool(llm=shared_llm)
        self.capabilities_tip = CAPABILITIES_TIP

    def analyze_emails(
        self, payload_messages: List[Any], query: str, sender_email: str | None
    ) -> Dict[str, Any]:
        """
        Analyze emails using appropriate tools based on query
        
        Args:
            payload_messages: List of email messages to analyze
            query: User's query or instruction
            sender_email: Optional sender email filter
            
        Returns:
            Dictionary with analysis results from all executed tools
        """
        # Convert messages to dict format if needed
        tool_messages = [
            msg if isinstance(msg, dict) else msg.dict(by_alias=True)  # type: ignore[union-attr]
            for msg in payload_messages
        ]
        effective_messages = tool_messages or fetch_recent_emails()
        
        # Plan which tools to use based on query using LangChain
        plan = self.chain.plan_tools(query, bool(tool_messages))
        
        # Execute tools according to plan
        result = self._run_plan(effective_messages, plan, query or "")
        
        # Persist results to database if messages were provided
        if tool_messages and result.get("filter_results"):
            self._persist_memory(tool_messages, {"emails": result["filter_results"]})
        
        result["capabilities_tip"] = self.capabilities_tip
        return result

    def weekly_summary(
        self, query: str, messages: List[Dict[str, Any]] | None = None
    ) -> Dict[str, Any]:
        """
        Generate weekly summary report
        
        Args:
            query: Summary query (defaults to weekly report)
            messages: Optional list of messages (falls back to database)
            
        Returns:
            Dictionary with weekly report and analysis
        """
        # Format messages if provided, otherwise fetch from database
        if messages:
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    formatted_messages.append({
                        "id": msg.get("id", ""),
                        "subject": msg.get("subject", ""),
                        "snippet": msg.get("snippet", ""),
                        "from": msg.get("from") or msg.get("from_", ""),
                        "body": msg.get("body", msg.get("snippet", "")),
                    })
                else:
                    # Pydantic model
                    formatted_messages.append({
                        "id": getattr(msg, "id", ""),
                        "subject": getattr(msg, "subject", ""),
                        "snippet": getattr(msg, "snippet", ""),
                        "from": getattr(msg, "from_", "") or getattr(msg, "from", ""),
                        "body": getattr(msg, "body", getattr(msg, "snippet", "")),
                    })
            messages_to_use = formatted_messages
        else:
            messages_to_use = fetch_recent_emails()
        
        if not messages_to_use:
            return {
                "summary": "Нет писем за неделю.",
                "messages": [
                    {"role": "agent", "tool": "weekly", "content": "Не найдено писем за последние 7 дней."}
                ],
                "capabilities_tip": self.capabilities_tip,
            }
        
        plan = self.chain.plan_tools(query or "Недельный отчёт", has_selected=bool(messages))
        result = self._run_plan(messages_to_use, plan, query or "Недельный отчёт")
        result["capabilities_tip"] = self.capabilities_tip
        return result


    def _run_plan(
        self, messages: List[Dict[str, Any]], plan: Sequence[str], query: str
    ) -> Dict[str, Any]:
        """
        Execute tools according to plan
        
        Args:
            messages: Email messages to process
            plan: List of tool names to execute
            query: User's query
            
        Returns:
            Aggregated results from all tools
        """
        response = {
            "summary": "",
            "key_tasks": [],
            "deadlines": [],
            "draft_reply": "",
            "filter_results": [],
            "newsletter_insights": {},
            "auto_replies": [],
            "weekly_report": "",
            "messages": [],
        }
        filter_result = {}
        newsletter_result = {}
        
        # Execute each tool in plan using LangChain when available
        for tool_name in plan:
            if tool_name == "filter":
                # Use LangChain chain for filtering
                try:
                    filter_result = self.chain.run_filtering(messages)
                except Exception:
                    # Fallback to tool if chain fails
                    filter_result = self.filter_tool.run(messages=messages)
                response["filter_results"] = filter_result.get("emails", [])
                response["messages"].append(
                    {
                        "role": "agent",
                        "tool": self.filter_tool.name,
                        "content": filter_result.get("summary", "Фильтрация выполнена."),
                    }
                )
            elif tool_name == "newsletter":
                # Newsletter tool needs filter results
                if not filter_result:
                    try:
                        filter_result = self.chain.run_filtering(messages)
                    except Exception:
                        filter_result = self.filter_tool.run(messages=messages)
                    response["filter_results"] = filter_result.get("emails", [])
                
                # Use LangChain chain for newsletter analysis
                try:
                    newsletter_result = self.chain.run_newsletter(
                        messages=messages,
                        filter_data=filter_result,
                        weekly_metrics=get_weekly_metrics(),
                    )
                except Exception:
                    # Fallback to tool
                    newsletter_result = self.newsletter_tool.run(
                        messages=messages,
                        filter_data=filter_result,
                        weekly_metrics=get_weekly_metrics(),
                    )
                
                response["newsletter_insights"] = newsletter_result
                response["weekly_report"] = newsletter_result.get("weekly_report", "")
                digest_text = (
                    newsletter_result.get("digest")
                    or newsletter_result.get("weekly_report")
                    or "Digest сформирован."
                )
                response["messages"].append(
                    {
                        "role": "agent",
                        "tool": self.newsletter_tool.name,
                        "content": digest_text,
                    }
                )
            elif tool_name == "auto":
                # Auto-reply tool needs filter results
                if not filter_result:
                    try:
                        filter_result = self.chain.run_filtering(messages)
                    except Exception:
                        filter_result = self.filter_tool.run(messages=messages)
                    response["filter_results"] = filter_result.get("emails", [])
                
                # Use LangChain chain for auto-reply
                try:
                    auto_reply_result = self.chain.run_auto_reply(
                        messages=messages, filter_data=filter_result
                    )
                except Exception:
                    # Fallback to tool
                    auto_reply_result = self.auto_reply_tool.run(
                        messages=messages, filter_data=filter_result
                    )
                
                response["auto_replies"] = auto_reply_result.get("templates", [])
                summary = f"Подготовлено {len(response['auto_replies'])} шаблонов автоответов."
                response["messages"].append({
                    "role": "agent",
                    "tool": self.auto_reply_tool.name,
                    "content": summary,
                })
            elif tool_name == "content":
                # Use LangChain chain for content analysis
                try:
                    content_result = self.chain.run_content_analysis(
                        messages=messages, query=query
                    )
                except Exception:
                    # Fallback to tool
                    content_result = self.content_tool.run(messages=messages, user_query=query)
                
                response["summary"] = content_result.get("summary") or response["summary"]
                response["key_tasks"] = content_result.get("key_tasks", [])
                response["deadlines"] = content_result.get("deadlines", [])
                response["draft_reply"] = content_result.get("draft_reply", "")
                response["messages"].append(
                    {
                        "role": "agent",
                        "tool": self.content_tool.name,
                        "content": response["summary"] or "Анализ завершён.",
                    }
                )
        
        # Ensure response has at least one message
        if not response["messages"] and response["summary"]:
            response["messages"].append({
                "role": "agent",
                "tool": "summary",
                "content": response["summary"],
            })
        if not response["summary"] and response["messages"]:
            response["summary"] = response["messages"][-1]["content"]
        
        return response

    def _persist_memory(
        self, messages: List[Dict[str, Any]], filter_result: Dict[str, Any]
    ) -> None:
        """
        Persist email analysis results to database
        
        Args:
            messages: Original email messages
            filter_result: Filter tool results with categorization
        """
        email_map = {msg.get("id"): msg for msg in messages if msg.get("id")}
        records = []
        for item in filter_result.get("emails", []):
            msg = email_map.get(item.get("id"))
            if not msg:
                continue
            records.append(
                {
                    "id": item.get("id"),
                    "sender_email": msg.get("from") or msg.get("from_"),
                    "subject": msg.get("subject"),
                    "snippet": msg.get("snippet"),
                    "body": msg.get("body"),
                    "email_type": item.get("type"),
                    "priority": item.get("priority"),
                    "requires_reply": item.get("requires_reply"),
                    "tags": item.get("tags"),
                    "metadata": item,
                }
            )
        if records:
            store_email_memory(records)

