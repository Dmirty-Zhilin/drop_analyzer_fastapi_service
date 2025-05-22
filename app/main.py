from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import analysis, reports  # Import the reports router

app = FastAPI(title="Drop Domain Analyzer API", version="0.1.0")

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://qo8k8k0c48sk080ccwgswocg.alettidesign.ru"],  # Домен фронтенда
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to Drop Domain Analyzer API"}

# Include the analysis router
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis Tasks"])

# Include the reports router
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
