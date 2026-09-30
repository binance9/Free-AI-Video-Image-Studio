AI VIDEO DIRECTOR V6.4.1 - CHARACTER REFERENCE ROUTE FIX

- Adds POST/GET/DELETE /api/ai-video-director/reference
- Adds compatibility alias /api/ai-video-director/character-reference
- Frontend retries alias only on HTTP 404
- status reports character_reference_api=true
- cache bust v=641

Scope: AI Director only. AI core, models, SDXL, tao_anh_ai, tao_video_ai are not overwritten.

Install: extract at ai_video_factory root, run INSTALL_AI_VIDEO_DIRECTOR_V6_4_1.bat, fully restart bot, Ctrl+F5.
