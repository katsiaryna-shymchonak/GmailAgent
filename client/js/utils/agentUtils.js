/**
 * Utility functions for agent response normalization and tool usage summary
 * client/js/utils/agentUtils.js
 */

export function summarizeToolUsage(data) {
  if (!data || typeof data !== 'object') return '';

  const executed = Array.isArray(data.executed_tools) ? data.executed_tools : [];
  if (!executed.length) return '';

  const map = {
    filter: 'Filtering',
    content: 'Content',
    key_points: 'Key Points',
    deadlines: 'Deadlines',
    auto: 'Auto-replies',
    newsletter: 'Newsletters',
  };

  const used = executed.map((t) => map[t] || t);
  return used.length ? `Tools used: ${used.join(', ')}` : '';
}

export function ensureDataShape(data) {
  const defaults = {
    summary: '',
    filter_results: [],
    newsletter_insights: { unsubscribe: [], keep: [], digest: '', weekly_report: null },
    auto_replies: [],
    messages: [],
    capabilities_tip: '',
    key_points: [],
    key_tasks: [],
    deadlines: [],
    draft_reply: {},
    weekly_report: '',
    executed_tools: [],
  };

  if (!data || typeof data !== 'object') return defaults;

  const safe = { ...defaults };

  // Scalars
  safe.summary = typeof data.summary === 'string' ? data.summary : defaults.summary;
  safe.capabilities_tip =
    typeof data.capabilities_tip === 'string' ? data.capabilities_tip : defaults.capabilities_tip;
  safe.weekly_report =
    typeof data.weekly_report === 'string' ? data.weekly_report : defaults.weekly_report;

  // Arrays
  safe.filter_results = Array.isArray(data.filter_results) ? data.filter_results : defaults.filter_results;
  safe.auto_replies = Array.isArray(data.auto_replies) ? data.auto_replies : defaults.auto_replies;

  // Key points (строки превращаем в массив)
  safe.key_points = Array.isArray(data.key_points)
    ? data.key_points.map((p) => ({
        email_id: p.email_id || p.id || '',
        points: Array.isArray(p.points)
          ? p.points
          : p.points
          ? [String(p.points)]
          : []
      }))
    : [];

  // Key tasks (без deadline)
  safe.key_tasks = Array.isArray(data.key_tasks)
    ? data.key_tasks.map((t) => ({
        email_id: t.email_id || t.id || '',
        task: t.task || ''
      }))
    : [];

  // Deadlines
  safe.deadlines = Array.isArray(data.deadlines)
    ? data.deadlines.map((d) => ({
        email_id: d.email_id || d.id || '',
        deadline: d.deadline || '',
        description: d.description || ''
      }))
    : [];

  // Objects
  safe.newsletter_insights =
    data.newsletter_insights && typeof data.newsletter_insights === 'object' && !Array.isArray(data.newsletter_insights)
      ? {
          unsubscribe: Array.isArray(data.newsletter_insights.unsubscribe) ? data.newsletter_insights.unsubscribe : [],
          keep: Array.isArray(data.newsletter_insights.keep) ? data.newsletter_insights.keep : [],
          digest: typeof data.newsletter_insights.digest === 'string' ? data.newsletter_insights.digest : '',
          weekly_report:
            typeof data.newsletter_insights.weekly_report === 'string' ||
            data.newsletter_insights.weekly_report === null
              ? data.newsletter_insights.weekly_report
              : null,
        }
      : defaults.newsletter_insights;

  safe.draft_reply =
    data.draft_reply && typeof data.draft_reply === 'object' && !Array.isArray(data.draft_reply)
      ? data.draft_reply
      : defaults.draft_reply;

  // executed_tools
  safe.executed_tools = Array.isArray(data.executed_tools) ? data.executed_tools : defaults.executed_tools;

  // Messages normalization
  safe.messages =
    Array.isArray(data.messages) && data.messages.length
      ? data.messages
          .filter((m) => m && typeof m === 'object')
          .map((m) => ({
            role: typeof m.role === 'string' ? m.role : 'agent',
            tool: typeof m.tool === 'string' ? m.tool : '',
            content: typeof m.content === 'string' ? m.content : '',
          }))
      : defaults.messages;

  return safe;
}
