from faster_whisper import WhisperModel
import os
from tqdm import tqdm  # 导入进度条库

# ====== 配置 ======
VIDEO_FOLDER = r"E:\BaiduSyncdisk\Obsidian\Tiktok\0_Inbox\Video_Raw"
OUTPUT_FOLDER = r"E:\BaiduSyncdisk\Obsidian\Tiktok\0_Inbox\Temp_Transcripts"

# ====== Whisper模型 ======
model = WhisperModel(
    "large-v3",
    device="cuda",          # 使用NVIDIA显卡加速
    compute_type="float16"  # 显存足够用float16，不足可用int8
)

# 创建输出目录
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 支持的视频格式
video_exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

# 获取所有待处理的视频文件列表
video_files = [f for f in os.listdir(VIDEO_FOLDER) if any(f.lower().endswith(ext) for ext in video_exts)]

# ====== 批量处理 ======
# 外层进度条：展示整体文件处理进度
for filename in tqdm(video_files, desc="总体处理进度"):
    try:
        video_path = os.path.join(VIDEO_FOLDER, filename)
        
        # 执行转录
        segments, info = model.transcribe(
            video_path,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False
        )
        
        full_text = ""
        segment_list = list(segments) # 将生成器转为列表，以便计算长度
        
        # 内层进度条：展示当前视频的字幕段落提取进度
        with tqdm(total=len(segment_list), desc=f"正在识别 {filename}", leave=False) as pbar:
            for segment in segment_list:
                full_text += segment.text.strip() + "\n"
                pbar.update(1) # 每处理一段字幕，进度条走一格

        txt_name = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(OUTPUT_FOLDER, txt_name)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)

    except Exception as e:
        print(f"\n❌ 错误: {filename}")
        print(e)

print("\n🎉 全部完成！")