AI VIDEO DIRECTOR V7 - MEMORY

Memory layers:
1) VIDEO PLAYBOOK: permanent production principles, loaded before every plan.
2) PROJECT MEMORY: project-specific style/reference/voice/platform identifiers.
3) FEEDBACK MEMORY: explicit user feedback only; never blindly learns every output.

Priority:
USER COMMAND > PROJECT MEMORY > VIDEO PLAYBOOK > FEEDBACK MEMORY > MODEL DEFAULTS

New API:
GET  /api/ai-video-director/memory/status
GET  /api/ai-video-director/memory/context?project_id=...
POST /api/ai-video-director/memory/project
POST /api/ai-video-director/memory/feedback

Local storage:
data/ai_video_director/memory/video_playbook.json
data/ai_video_director/memory/project_memory.json
data/ai_video_director/memory/feedback_memory.json

Install:
Extract ZIP into ai_video_factory root and run INSTALL_AI_VIDEO_DIRECTOR_V7_MEMORY.bat.
Then restart backend/app.
