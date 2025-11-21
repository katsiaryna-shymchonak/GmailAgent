"""LangChain integration for agent processing"""
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import get_settings
from ..tools.utils import format_messages

settings = get_settings()


class AgentChain:
    """LangChain-based agent for processing email analysis requests"""
    
    def __init__(self):
        """Initialize LangChain with Gemini model"""
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0.2,
            google_api_key=settings.gemini_api_key,
        )
        self._setup_chains()
    
    def _setup_chains(self):
        """Setup LangChain prompt templates and chains"""
        # Tool planning chain - determines which tools to use
        self.planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI email assistant. Analyze the user's query and determine which tools to use.
Available tools: filter, newsletter, content, auto_reply.
Return a JSON list of tool names to execute in order.
Example: ["filter", "content"]"""),
            ("human", "{query}")
        ])
        
        # Content analysis chain
        self.content_analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are analyzing emails. Extract key information, tasks, deadlines, and generate a summary.
Return JSON with: summary, key_tasks, deadlines, draft_reply."""),
            ("human", "Query: {query}\n\nEmails:\n{emails}")
        ])
        
        # Filtering chain
        self.filtering_prompt = ChatPromptTemplate.from_messages([
            ("system", """Categorize and prioritize emails. For each email determine:
type (meeting|newsletter|personal|work), priority (high|normal|low), requires_reply, tags, actions.
Return JSON with: emails (array), summary, high_priority_ids."""),
            ("human", "Emails:\n{emails}")
        ])
        
        # Newsletter chain
        self.newsletter_prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze newsletters and provide recommendations. Return JSON with:
unsubscribe (array), keep (array), digest, weekly_report, metrics_used."""),
            ("human", "Email classification: {filter_data}\n\nWeekly metrics: {metrics}")
        ])
        
        # Auto-reply chain
        self.auto_reply_prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate personalized auto-reply templates. Return JSON with:
templates (array with id, subject, type, template, notes), general_templates."""),
            ("human", "Email classification: {filter_data}")
        ])
    
    def plan_tools(self, query: str, has_selected: bool = False) -> List[str]:
        """
        Plan which tools to execute based on query
        
        Args:
            query: User's query
            has_selected: Whether user selected specific emails
            
        Returns:
            List of tool names to execute
        """
        # Use keyword-based planning for reliability
        q = (query or "").lower()
        plan = []
        
        def add(tool: str):
            if tool not in plan:
                plan.append(tool)
        
        keywords = {
            "meeting": "filter", "митинг": "filter", "созв": "filter",
            "tag": "filter", "filter": "filter",
            "рассыл": "newsletter", "digest": "newsletter", "недель": "newsletter",
            "summary": "content", "резюме": "content", "задач": "content",
            "deadline": "content", "дедлай": "content",
            "ответ": "auto", "auto": "auto", "шаблон": "auto",
        }
        
        for key, tool in keywords.items():
            if key in q:
                add(tool)
        
        if not plan:
            add("content")
        
        # Ensure dependencies
        if "newsletter" in plan and "filter" not in plan:
            plan.insert(0, "filter")
        if "auto" in plan and "filter" not in plan:
            plan.insert(0, "filter")
        
        if not has_selected and "newsletter" not in plan:
            plan.append("newsletter")
        
        return plan
    
    def run_filtering(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run filtering tool using LangChain
        
        Args:
            messages: List of email messages
            
        Returns:
            Filtering results with categorized emails
        """
        emails_text = format_messages(messages)
        try:
            # Try with structured output for reliable JSON
            chain = self.filtering_prompt | self.llm.with_structured_output(dict)
            result = chain.invoke({"emails": emails_text})
            return result if isinstance(result, dict) else {}
        except Exception:
            # Fallback to regular invocation
            chain = self.filtering_prompt | self.llm
            response = chain.invoke({"emails": emails_text})
            content = response.content if hasattr(response, 'content') else str(response)
            import json
            try:
                return json.loads(content) if isinstance(content, str) else {}
            except json.JSONDecodeError:
                return {"raw": content, "emails": [], "summary": ""}
    
    def run_content_analysis(
        self, messages: List[Dict[str, Any]], query: str
    ) -> Dict[str, Any]:
        """
        Run content analysis using LangChain
        
        Args:
            messages: List of email messages
            query: User's query
            
        Returns:
            Content analysis results
        """
        emails_text = format_messages(messages)
        try:
            chain = self.content_analysis_prompt | self.llm.with_structured_output(dict)
            result = chain.invoke({"query": query or "Summarize these emails", "emails": emails_text})
            return result if isinstance(result, dict) else {}
        except Exception:
            chain = self.content_analysis_prompt | self.llm
            response = chain.invoke({"query": query or "Summarize these emails", "emails": emails_text})
            content = response.content if hasattr(response, 'content') else str(response)
            import json
            try:
                return json.loads(content) if isinstance(content, str) else {}
            except json.JSONDecodeError:
                return {"summary": content, "key_tasks": [], "deadlines": [], "draft_reply": ""}
    
    def run_newsletter(
        self,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        weekly_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run newsletter analysis using LangChain
        
        Args:
            messages: List of email messages
            filter_data: Filtered email categorization
            weekly_metrics: Weekly email statistics
            
        Returns:
            Newsletter insights and recommendations
        """
        import json
        try:
            chain = self.newsletter_prompt | self.llm.with_structured_output(dict)
            result = chain.invoke({
                "filter_data": json.dumps(filter_data.get('emails', []), ensure_ascii=False),
                "metrics": json.dumps(weekly_metrics, default=str, ensure_ascii=False)
            })
            return result if isinstance(result, dict) else {}
        except Exception:
            chain = self.newsletter_prompt | self.llm
            response = chain.invoke({
                "filter_data": json.dumps(filter_data.get('emails', []), ensure_ascii=False),
                "metrics": json.dumps(weekly_metrics, default=str, ensure_ascii=False)
            })
            content = response.content if hasattr(response, 'content') else str(response)
            try:
                return json.loads(content) if isinstance(content, str) else {}
            except json.JSONDecodeError:
                return {"unsubscribe": [], "keep": [], "digest": "", "weekly_report": "", "metrics_used": {}}
    
    def run_auto_reply(
        self, messages: List[Dict[str, Any]], filter_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run auto-reply generation using LangChain
        
        Args:
            messages: List of email messages
            filter_data: Filtered email categorization
            
        Returns:
            Auto-reply templates
        """
        import json
        try:
            chain = self.auto_reply_prompt | self.llm.with_structured_output(dict)
            result = chain.invoke({
                "filter_data": json.dumps(filter_data.get('emails', []), ensure_ascii=False)
            })
            return result if isinstance(result, dict) else {}
        except Exception:
            chain = self.auto_reply_prompt | self.llm
            response = chain.invoke({
                "filter_data": json.dumps(filter_data.get('emails', []), ensure_ascii=False)
            })
            content = response.content if hasattr(response, 'content') else str(response)
            try:
                return json.loads(content) if isinstance(content, str) else {}
            except json.JSONDecodeError:
                return {"templates": [], "general_templates": []}

