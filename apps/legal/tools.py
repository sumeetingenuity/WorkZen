"""
Auto-generated tools for Legal Manager.
"""
from core.decorators import agent_tool
from asgiref.sync import sync_to_async
from .models import Case, Client, Contract, CourtDate, Document, Invoice

def _to_dict(obj):
    data = {}
    for field in obj._meta.fields:
        data[field.name] = getattr(obj, field.name)
    return data

@agent_tool(
    name="create_client",
    description="Create a new Client",
    log_response_to_orm=True,
    category="legal"
)
async def create_client(name: str, email: str = None, phone: str = None, address: str = None, notes: str = None) -> dict:
    obj = await sync_to_async(Client.objects.create)(**{k: v for k, v in locals().items() if k != 'obj'})
    return {"id": str(obj.id), "display_markdown": f"✅ Created {obj}"}

@agent_tool(
    name="get_client",
    description="Get Client by ID",
    log_response_to_orm=True,
    category="legal"
)
async def get_client(id: str) -> dict:
    obj = await sync_to_async(Client.objects.get)(id=id)
    return {"data": _to_dict(obj), "display_markdown": f"✅ Loaded {obj}"}

@agent_tool(
    name="search_clients",
    description="Search Clients by criteria",
    log_response_to_orm=True,
    category="legal"
)
async def search_clients(limit: int = 20) -> dict:
    qs = await sync_to_async(list)(Client.objects.all()[:limit])
    return {"results": [_to_dict(o) for o in qs], "display_markdown": f"✅ Found {len(qs)}"}

@agent_tool(
    name="update_client",
    description="Update an existing Client",
    log_response_to_orm=True,
    category="legal"
)
async def update_client(id: str, name: str, email: str = None, phone: str = None, address: str = None, notes: str = None) -> dict:
    obj = await sync_to_async(Client.objects.get)(id=id)
    for k, v in locals().items():
            if k not in ('id', 'obj') and v is not None:
                setattr(obj, k, v)
    await sync_to_async(obj.save)()
    return {"id": str(obj.id), "display_markdown": f"✅ Updated {obj}"}

@agent_tool(
    name="delete_client",
    description="Delete a Client",
    log_response_to_orm=True,
    category="legal"
)
async def delete_client(id: str) -> dict:
    obj = await sync_to_async(Client.objects.get)(id=id)
    await sync_to_async(obj.delete)()
    return {"status": "deleted", "display_markdown": "✅ Deleted"}

@agent_tool(
    name="create_case",
    description="Create a new Case",
    log_response_to_orm=True,
    category="legal"
)
async def create_case(title: str, status: str, client: str, description: str = None, court_date: str = None) -> dict:
    obj = await sync_to_async(Case.objects.create)(**{k: v for k, v in locals().items() if k != 'obj'})
    return {"id": str(obj.id), "display_markdown": f"✅ Created {obj}"}

@agent_tool(
    name="get_case",
    description="Get Case by ID",
    log_response_to_orm=True,
    category="legal"
)
async def get_case(id: str) -> dict:
    obj = await sync_to_async(Case.objects.get)(id=id)
    return {"data": _to_dict(obj), "display_markdown": f"✅ Loaded {obj}"}

@agent_tool(
    name="search_cases",
    description="Search Cases by criteria",
    log_response_to_orm=True,
    category="legal"
)
async def search_cases(limit: int = 20) -> dict:
    qs = await sync_to_async(list)(Case.objects.all()[:limit])
    return {"results": [_to_dict(o) for o in qs], "display_markdown": f"✅ Found {len(qs)}"}

@agent_tool(
    name="update_case",
    description="Update an existing Case",
    log_response_to_orm=True,
    category="legal"
)
async def update_case(id: str, title: str, status: str, client: str, description: str = None, court_date: str = None) -> dict:
    obj = await sync_to_async(Case.objects.get)(id=id)
    for k, v in locals().items():
            if k not in ('id', 'obj') and v is not None:
                setattr(obj, k, v)
    await sync_to_async(obj.save)()
    return {"id": str(obj.id), "display_markdown": f"✅ Updated {obj}"}

@agent_tool(
    name="delete_case",
    description="Delete a Case",
    log_response_to_orm=True,
    category="legal"
)
async def delete_case(id: str) -> dict:
    obj = await sync_to_async(Case.objects.get)(id=id)
    await sync_to_async(obj.delete)()
    return {"status": "deleted", "display_markdown": "✅ Deleted"}

@agent_tool(
    name="create_document",
    description="Create a new Document",
    log_response_to_orm=True,
    category="legal"
)
async def create_document(title: str, file: str, document_type: str, notes: str = None) -> dict:
    obj = await sync_to_async(Document.objects.create)(**{k: v for k, v in locals().items() if k != 'obj'})
    return {"id": str(obj.id), "display_markdown": f"✅ Created {obj}"}

@agent_tool(
    name="get_document",
    description="Get Document by ID",
    log_response_to_orm=True,
    category="legal"
)
async def get_document(id: str) -> dict:
    obj = await sync_to_async(Document.objects.get)(id=id)
    return {"data": _to_dict(obj), "display_markdown": f"✅ Loaded {obj}"}

@agent_tool(
    name="search_documents",
    description="Search Documents by criteria",
    log_response_to_orm=True,
    category="legal"
)
async def search_documents(limit: int = 20) -> dict:
    qs = await sync_to_async(list)(Document.objects.all()[:limit])
    return {"results": [_to_dict(o) for o in qs], "display_markdown": f"✅ Found {len(qs)}"}

@agent_tool(
    name="update_document",
    description="Update an existing Document",
    log_response_to_orm=True,
    category="legal"
)
async def update_document(id: str, title: str, file: str, document_type: str, notes: str = None) -> dict:
    obj = await sync_to_async(Document.objects.get)(id=id)
    for k, v in locals().items():
            if k not in ('id', 'obj') and v is not None:
                setattr(obj, k, v)
    await sync_to_async(obj.save)()
    return {"id": str(obj.id), "display_markdown": f"✅ Updated {obj}"}

@agent_tool(
    name="delete_document",
    description="Delete a Document",
    log_response_to_orm=True,
    category="legal"
)
async def delete_document(id: str) -> dict:
    obj = await sync_to_async(Document.objects.get)(id=id)
    await sync_to_async(obj.delete)()
    return {"status": "deleted", "display_markdown": "✅ Deleted"}

@agent_tool(
    name="create_contract",
    description="Create a new Contract",
    log_response_to_orm=True,
    category="legal"
)
async def create_contract(title: str, signed: bool, template: str = None, generated_text: str = None, signed_at: str = None) -> dict:
    obj = await sync_to_async(Contract.objects.create)(**{k: v for k, v in locals().items() if k != 'obj'})
    return {"id": str(obj.id), "display_markdown": f"✅ Created {obj}"}

@agent_tool(
    name="get_contract",
    description="Get Contract by ID",
    log_response_to_orm=True,
    category="legal"
)
async def get_contract(id: str) -> dict:
    obj = await sync_to_async(Contract.objects.get)(id=id)
    return {"data": _to_dict(obj), "display_markdown": f"✅ Loaded {obj}"}

@agent_tool(
    name="search_contracts",
    description="Search Contracts by criteria",
    log_response_to_orm=True,
    category="legal"
)
async def search_contracts(limit: int = 20) -> dict:
    qs = await sync_to_async(list)(Contract.objects.all()[:limit])
    return {"results": [_to_dict(o) for o in qs], "display_markdown": f"✅ Found {len(qs)}"}

@agent_tool(
    name="update_contract",
    description="Update an existing Contract",
    log_response_to_orm=True,
    category="legal"
)
async def update_contract(id: str, title: str, signed: bool, template: str = None, generated_text: str = None, signed_at: str = None) -> dict:
    obj = await sync_to_async(Contract.objects.get)(id=id)
    for k, v in locals().items():
            if k not in ('id', 'obj') and v is not None:
                setattr(obj, k, v)
    await sync_to_async(obj.save)()
    return {"id": str(obj.id), "display_markdown": f"✅ Updated {obj}"}

@agent_tool(
    name="delete_contract",
    description="Delete a Contract",
    log_response_to_orm=True,
    category="legal"
)
async def delete_contract(id: str) -> dict:
    obj = await sync_to_async(Contract.objects.get)(id=id)
    await sync_to_async(obj.delete)()
    return {"status": "deleted", "display_markdown": "✅ Deleted"}

@agent_tool(
    name="create_courtdate",
    description="Create a new CourtDate",
    log_response_to_orm=True,
    category="legal"
)
async def create_courtdate(name: str, description: str = None, status: str = None) -> dict:
    obj = await sync_to_async(CourtDate.objects.create)(**{k: v for k, v in locals().items() if k != 'obj'})
    return {"id": str(obj.id), "display_markdown": f"✅ Created {obj}"}

@agent_tool(
    name="get_courtdate",
    description="Get CourtDate by ID",
    log_response_to_orm=True,
    category="legal"
)
async def get_courtdate(id: str) -> dict:
    obj = await sync_to_async(CourtDate.objects.get)(id=id)
    return {"data": _to_dict(obj), "display_markdown": f"✅ Loaded {obj}"}

@agent_tool(
    name="search_courtdates",
    description="Search CourtDates by criteria",
    log_response_to_orm=True,
    category="legal"
)
async def search_courtdates(limit: int = 20) -> dict:
    qs = await sync_to_async(list)(CourtDate.objects.all()[:limit])
    return {"results": [_to_dict(o) for o in qs], "display_markdown": f"✅ Found {len(qs)}"}

@agent_tool(
    name="update_courtdate",
    description="Update an existing CourtDate",
    log_response_to_orm=True,
    category="legal"
)
async def update_courtdate(id: str, name: str, description: str = None, status: str = None) -> dict:
    obj = await sync_to_async(CourtDate.objects.get)(id=id)
    for k, v in locals().items():
            if k not in ('id', 'obj') and v is not None:
                setattr(obj, k, v)
    await sync_to_async(obj.save)()
    return {"id": str(obj.id), "display_markdown": f"✅ Updated {obj}"}

@agent_tool(
    name="delete_courtdate",
    description="Delete a CourtDate",
    log_response_to_orm=True,
    category="legal"
)
async def delete_courtdate(id: str) -> dict:
    obj = await sync_to_async(CourtDate.objects.get)(id=id)
    await sync_to_async(obj.delete)()
    return {"status": "deleted", "display_markdown": "✅ Deleted"}

@agent_tool(
    name="create_invoice",
    description="Create a new Invoice",
    log_response_to_orm=True,
    category="legal"
)
async def create_invoice(name: str, description: str = None, status: str = None) -> dict:
    obj = await sync_to_async(Invoice.objects.create)(**{k: v for k, v in locals().items() if k != 'obj'})
    return {"id": str(obj.id), "display_markdown": f"✅ Created {obj}"}

@agent_tool(
    name="get_invoice",
    description="Get Invoice by ID",
    log_response_to_orm=True,
    category="legal"
)
async def get_invoice(id: str) -> dict:
    obj = await sync_to_async(Invoice.objects.get)(id=id)
    return {"data": _to_dict(obj), "display_markdown": f"✅ Loaded {obj}"}

@agent_tool(
    name="search_invoices",
    description="Search Invoices by criteria",
    log_response_to_orm=True,
    category="legal"
)
async def search_invoices(limit: int = 20) -> dict:
    qs = await sync_to_async(list)(Invoice.objects.all()[:limit])
    return {"results": [_to_dict(o) for o in qs], "display_markdown": f"✅ Found {len(qs)}"}

@agent_tool(
    name="update_invoice",
    description="Update an existing Invoice",
    log_response_to_orm=True,
    category="legal"
)
async def update_invoice(id: str, name: str, description: str = None, status: str = None) -> dict:
    obj = await sync_to_async(Invoice.objects.get)(id=id)
    for k, v in locals().items():
            if k not in ('id', 'obj') and v is not None:
                setattr(obj, k, v)
    await sync_to_async(obj.save)()
    return {"id": str(obj.id), "display_markdown": f"✅ Updated {obj}"}

@agent_tool(
    name="delete_invoice",
    description="Delete a Invoice",
    log_response_to_orm=True,
    category="legal"
)
async def delete_invoice(id: str) -> dict:
    obj = await sync_to_async(Invoice.objects.get)(id=id)
    await sync_to_async(obj.delete)()
    return {"status": "deleted", "display_markdown": "✅ Deleted"}

@agent_tool(
    name="case_intake",
    description="Execute case intake workflow",
    log_response_to_orm=True,
    category="legal"
)
async def case_intake() -> dict:
    return {"status": "not_implemented", "display_markdown": "⚠️ Not implemented"}

@agent_tool(
    name="document_review",
    description="Execute document review workflow",
    log_response_to_orm=True,
    category="legal"
)
async def document_review() -> dict:
    return {"status": "not_implemented", "display_markdown": "⚠️ Not implemented"}

@agent_tool(
    name="contract_generation",
    description="Execute contract generation workflow",
    log_response_to_orm=True,
    category="legal"
)
async def contract_generation() -> dict:
    return {"status": "not_implemented", "display_markdown": "⚠️ Not implemented"}

@agent_tool(
    name="court_reminder",
    description="Execute court reminder workflow",
    log_response_to_orm=True,
    category="legal"
)
async def court_reminder() -> dict:
    return {"status": "not_implemented", "display_markdown": "⚠️ Not implemented"}
