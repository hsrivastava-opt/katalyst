"""Progress for the existing prototype workflow, not the future SRS-to-Jira pipeline."""


def summary(project):
    approvals = project['approvals']
    g0 = approvals.get('g0', {}).get('decision') == 'approved'
    g1 = g0 and approvals.get('g1', {}).get('decision') == 'approved'
    g2 = g1 and approvals.get('g2', {}).get('decision') == 'approved'
    tab = 'handoff' if g2 else 'prototype' if g1 else 'stories' if g0 else 'capture'
    stage = {
        'capture': 'Requirements review' if project['requirements'] else 'Requirements intake',
        'stories': 'Story review' if project['stories'] else 'Story generation',
        'prototype': 'Prototype review' if project['prototype'] else 'Prototype generation',
        'handoff': 'Engineering handoff',
    }[tab]
    return {
        'current_stage': stage,
        'completion_percentage': round(sum((g0, g1, g2)) / 3 * 100),
        'resume_tab': tab,
        'workflow_scope': 'prototype',
        'planning_status': 'foundation_ready',
    }


def project_summary(project):
    return {key: project.get(key, '') for key in (
        'id', 'title', 'description', 'brief', 'business_domain', 'created_at', 'updated_at', 'status'
    )} | summary(project)
