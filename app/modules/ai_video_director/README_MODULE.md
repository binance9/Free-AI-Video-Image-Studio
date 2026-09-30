# ai_video_director V5

Quality-first orchestration layer for AI Video Factory.

Pipeline:
idea/script -> storyboard -> character anchor -> scene image -> image QA -> image-to-video -> video QA -> repair failed scene only -> assembly -> voice/music -> final 1080p master -> final QA.

It keeps `tao_anh_ai`, `tao_video_ai`, music and edit modules independent and calls their services rather than duplicating their logic.
