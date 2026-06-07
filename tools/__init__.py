from tools.calculator import calculator, CALCULATOR_SCHEMA
from tools.web_search import web_search, WEB_SEARCH_SCHEMA
from tools.weather import get_weather, WEATHER_SCHEMA
from tools.news import get_news, NEWS_SCHEMA
from tools.file_analyzer import analyze_file, FILE_SCHEMA
from tools.code_interpreter import run_python_code, CODE_SCHEMA
from tools.vision import analyze_image, VISION_SCHEMA
from tools.document_generator import (
    generate_pdf,  GENERATE_PDF_SCHEMA,
    generate_word, GENERATE_WORD_SCHEMA,
    generate_excel,GENERATE_EXCEL_SCHEMA,
    generate_pptx, GENERATE_PPTX_SCHEMA,
)
from tools.projects_tool import manage_project, MANAGE_PROJECT_SCHEMA
from tools.discord_webhook import send_discord, DISCORD_SCHEMA
from tools.script_runner import run_script, RUN_SCRIPT_SCHEMA
from tools.scheduler_tool import schedule_task, SCHEDULE_TASK_SCHEMA
from tools.browser import browse_web, BROWSE_WEB_SCHEMA

TOOLS_SCHEMAS = [
    CALCULATOR_SCHEMA,
    WEB_SEARCH_SCHEMA,
    WEATHER_SCHEMA,
    NEWS_SCHEMA,
    FILE_SCHEMA,
    CODE_SCHEMA,
    VISION_SCHEMA,
    GENERATE_PDF_SCHEMA,
    GENERATE_WORD_SCHEMA,
    GENERATE_EXCEL_SCHEMA,
    GENERATE_PPTX_SCHEMA,
    MANAGE_PROJECT_SCHEMA,
    DISCORD_SCHEMA,
    RUN_SCRIPT_SCHEMA,
    SCHEDULE_TASK_SCHEMA,
    BROWSE_WEB_SCHEMA,
]

TOOLS_FUNCTIONS = {
    "calculator":    calculator,
    "web_search":    web_search,
    "get_weather":   get_weather,
    "get_news":      get_news,
    "analyze_file":  analyze_file,
    "run_python_code": run_python_code,
    "analyze_image": analyze_image,
    "generate_pdf":  generate_pdf,
    "generate_word": generate_word,
    "generate_excel":generate_excel,
    "generate_pptx": generate_pptx,
    "manage_project":manage_project,
    "send_discord":  send_discord,
    "run_script":    run_script,
    "schedule_task":  schedule_task,
    "browse_web":     browse_web,
}

TOOLS_ICONS = {
    "calculator":     "🧮",
    "web_search":     "🔍",
    "get_weather":    "🌤️",
    "get_news":       "📰",
    "analyze_file":   "📄",
    "run_python_code":"⚙️",
    "analyze_image":  "👁️",
    "generate_pdf":   "📕",
    "generate_word":  "📝",
    "generate_excel": "📊",
    "generate_pptx":  "📽️",
    "manage_project": "📋",
    "send_discord":   "💬",
    "run_script":     "▶️",
    "schedule_task":  "⏰",
    "browse_web":     "🌐",
}
