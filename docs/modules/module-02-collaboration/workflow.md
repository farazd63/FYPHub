# Module 2 workflow

Team registration creates a cycle-scoped team after the active group-size and ownership checks pass. The team lifecycle is handled by the current team and project-workflow services.

When a supervisor assignment is active, the backend ensures one assignment-scoped collaboration channel for that team and supervisor. Students and supervisors access that channel through their role-specific collaboration endpoints; reassignment archives the previous channel and creates the new assignment channel.

The student progress dashboard reads project milestones, tasks, supervision meetings, and the assigned supervisor through the project-workflow API. The student AI assistant is a separate team-scoped advisory workflow backed by its own conversation/message models.
