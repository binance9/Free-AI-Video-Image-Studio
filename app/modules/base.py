from dataclasses import dataclass

@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    label: str
    responsibility: str

MODULES = [
    ModuleDefinition("script", "Script Engine", "Viết và chuẩn hóa kịch bản"),
    ModuleDefinition("character", "Character Engine", "Tạo và giữ nhất quán nhân vật"),
    ModuleDefinition("storyboard", "Storyboard Engine", "Chia cảnh, shot và prompt hình ảnh"),
    ModuleDefinition("video", "Video Engine", "Điều phối sinh video qua provider/local model"),
    ModuleDefinition("voice", "Voice Engine", "Giọng đọc, hội thoại và voice identity"),
    ModuleDefinition("lipsync", "Lip-sync Engine", "Đồng bộ khẩu hình"),
    ModuleDefinition("translation", "Translation Engine", "Dịch đa ngôn ngữ"),
    ModuleDefinition("subtitle", "Subtitle Engine", "Tạo và căn thời gian phụ đề"),
    ModuleDefinition("editor", "Editor Engine", "Ghép shot, âm thanh, chuyển cảnh và render"),
    ModuleDefinition("quality", "Quality Control", "Chấm chất lượng và yêu cầu retry"),
    ModuleDefinition("memory", "Project Memory", "Lưu trạng thái, nhân vật, quyết định và lịch sử"),
    ModuleDefinition("cost", "Cost Controller", "Theo dõi ngân sách và chọn phương án tối ưu"),
    ModuleDefinition("provider", "Provider Manager", "Trừu tượng hóa API/model để thay thế dễ dàng"),
]
