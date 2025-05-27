""" Улучшенная версия функции экспорта отчетов с исправлениями проблем PDF и обработки временных файлов """
import os
import io
import csv
import tempfile
import pandas as pd
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from weasyprint import HTML

# Временное хранилище отчетов (в реальном приложении должно быть заменено на базу данных)
fake_reports_db = {}

# Функция экспорта отчета
async def export_report(
    report_id: str,
    format: str = "excel",
    filter_type: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """ Экспортирует отчет в выбранном формате (excel, csv, pdf)
    с улучшенной обработкой ошибок и временных файлов
    """
    # Получаем данные отчета
    if report_id not in fake_reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report_data = fake_reports_db[report_id]
    
    # Подготовка данных для экспорта
    results = report_data["results"]
    
    # Фильтрация данных, если указан тип фильтра
    if filter_type == "long-live":
        results = [r for r in results if r.get("recommended", False)]
    
    # Проверка наличия данных после фильтрации
    if not results:
        raise HTTPException(status_code=404, detail="No data to export after filtering")
    
    # Преобразование данных в DataFrame
    data = []
    for result in results:
        row = {
            "Домен": result.get("domain", ""),
            "Всего снимков": result.get("total_snapshots", 0),
            "Первый снимок": result.get("first_snapshot", ""),
            "Последний снимок": result.get("last_snapshot", ""),
            "Лет охвата": result.get("years_covered", 0),
            "Средний интервал (дни)": result.get("avg_interval_days", 0),
            "Макс. разрыв (дни)": result.get("max_gap_days", 0),
            "Кол-во карт времени": result.get("timemap_count", 0),
            "Рекомендован": "Да" if result.get("recommended", False) else "Нет",
            "Оценка": result.get("assessment_score", 0),
            "Сводка": result.get("assessment_summary", "")
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Формирование базового имени файла
    filename_base = f"report_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if filter_type:
        filename_base += f"_{filter_type}"
    
    # Экспорт в выбранном формате
    if format.lower() == "excel":
        # Экспорт в Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Отчет', index=False)
            
            # Настройка форматирования
            workbook = writer.book
            worksheet = writer.sheets['Отчет']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Автоподбор ширины столбцов
            for i, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_width)
        
        output.seek(0)
        filename = f"{filename_base}.xlsx"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )
    
    elif format.lower() == "csv":
        # Экспорт в CSV с исправленной кодировкой
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC, encoding='utf-8')
        output.seek(0)
        filename = f"{filename_base}.csv"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers=headers
        )
    
    elif format.lower() == "pdf":
        try:
            # Проверка наличия шрифтов
            noto_font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
            wqy_font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
            font_family = ""
            
            if os.path.exists(noto_font_path):
                font_family += "'Noto Sans CJK SC', "
            if os.path.exists(wqy_font_path):
                font_family += "'WenQuanYi Zen Hei', "
            font_family += "Arial, sans-serif"
            
            # Создаем временный HTML файл
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Отчет по доменам</title>
                    <style>
                        body {{ font-family: {font_family}; margin: 20px; }}
                        h1 {{ color: #333; font-size: 24px; margin-bottom: 20px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background-color: #f2f2f2; font-weight: bold; }}
                        tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    </style>
                </head>
                <body>
                    <h1>Отчет по доменам {f"(Long-Live)" if filter_type == "long-live" else ""}</h1>
                    <table>
                        <thead>
                            <tr>
                                {"".join([f"<th>{col}</th>" for col in df.columns])}
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(["<tr>" + "".join([f"<td>{cell}</td>" for cell in row]) + "</tr>" for row in df.values.tolist()])}
                        </tbody>
                    </table>
                    <p>Дата создания: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                </body>
                </html>
                """
                temp_html.write(html_content.encode('utf-8'))
                temp_html_path = temp_html.name
            
            # Создаем PDF из HTML
            pdf_path = temp_html_path.replace('.html', '.pdf')
            HTML(temp_html_path).write_pdf(pdf_path)
            
            # Возвращаем PDF файл
            filename = f"{filename_base}.pdf"
            headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
            
            # Функция для очистки временных файлов
            def cleanup_temp_files():
                try:
                    if os.path.exists(temp_html_path):
                        os.unlink(temp_html_path)
                    if os.path.exists(pdf_path):
                        os.unlink(pdf_path)
                except Exception as e:
                    print(f"Error cleaning up temporary files: {e}")
            
            # Добавляем задачу очистки в фоновые задачи
            if background_tasks:
                background_tasks.add_task(cleanup_temp_files)
            
            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                headers=headers,
                background=BackgroundTasks() if not background_tasks else None
            )
        
        except Exception as e:
            # Очищаем временные файлы в случае ошибки
            if 'temp_html_path' in locals() and os.path.exists(temp_html_path):
                os.unlink(temp_html_path)
            if 'pdf_path' in locals() and os.path.exists(pdf_path):
                os.unlink(pdf_path)
            
            raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {format}. Supported formats: excel, csv, pdf"
        )
