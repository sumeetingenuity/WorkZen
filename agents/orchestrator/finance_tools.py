"""
Financial Tracking Tools - Agent-callable tools for ledger and budget management.
"""
import logging
from typing import Optional
from core.decorators import agent_tool
from core.models import FinancialEntry
from django.db.models import Sum
import datetime

logger = logging.getLogger(__name__)

@agent_tool(
    name="log_transaction",
    description="Record a financial transaction (income or expense).",
    category="productivity"
)
async def log_transaction(
    amount: float,
    description: str,
    category: str,
    currency: str = "USD",
    project: Optional[str] = None,
    _user_id: str = None
):
    """Records a transaction in the ledger."""
    entry = await FinancialEntry.objects.acreate(
        user_id=_user_id,
        transaction_date=datetime.date.today(),
        amount=amount,
        description=description,
        category=category.lower(),
        currency=currency,
        project=project
    )
    
    return {
        "status": "recorded",
        "entry_id": str(entry.id),
        "amount": f"{amount} {currency}",
        "description": description
    }

@agent_tool(
    name="get_financial_report",
    description="Get a summary of finances for a specific category or project.",
    category="productivity"
)
async def get_financial_report(category: Optional[str] = None, project: Optional[str] = None, _user_id: str = None):
    """Generates a simple financial summary."""
    qs = FinancialEntry.objects.filter(user_id=_user_id)
    if category:
        qs = qs.filter(category=category.lower())
    if project:
        qs = qs.filter(project=project)
        
    summary = await sync_to_async(qs.aggregate)(total=Sum('amount'))
    total_amount = summary.get('total') or 0
    
    # Get top transactions
    transactions = []
    async for t in qs.order_by('-transaction_date')[:10]:
        transactions.append({
            "date": t.transaction_date.isoformat(),
            "amount": float(t.amount),
            "desc": t.description
        })
        
    return {
        "total_expenditure": float(total_amount),
        "top_transactions": transactions,
        "filters": {"category": category, "project": project}
    }

# Helper inside the tool for async aggregate
from asgiref.sync import sync_to_async
