import os
from package.document.office_automator import automator, open_in_native_app
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class ExpenseGenius:
    """
    Handles converting receipt data to formatted Excel reports.
    Expects structured data from the Interpreter (which would use OCR/Vision).
    """
    AI_INSTRUCTION = (
        "To process receipts, use a Vision-capable LLM or OCR to extract a list of JSON objects "
        "with 'date', 'vendor', 'amount', and 'category'. Then pass it to expense_genius.process_receipts(data)."
    )

    def process_receipts(self, structured_data, output_filename="Expense_Report.xlsx"):
        # structured_data: list of dicts like {"date": "2023-01-01", "vendor": "Uber", "amount": 25.50, "category": "Travel"}
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        output_path = os.path.join(data_dir, output_filename)

        success = automator.create_excel_report(structured_data, output_path)
        if success:
            logger.info(f"Expense report generated successfully: {output_path}")
            open_in_native_app(output_path)
            return output_path
        return None

expense_genius = ExpenseGenius()

def run(jarvis_app, entities, **kwargs):
    # This would be called via intent dispatcher
    receipts_data = entities.get("receipts_data")
    if receipts_data:
        path = expense_genius.process_receipts(receipts_data)
        return f"费用报销单已生成并打开：{path}"
    return "未提供收据数据。"
