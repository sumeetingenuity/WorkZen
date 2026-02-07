# Tool Description Template for Generated Apps

## Purpose
This template ensures that all generated tools have comprehensive, LLM-friendly descriptions that prevent parameter validation errors.

## Template Structure

```python
@agent_tool(
    name="tool_name",
    description="""Brief one-line summary of what the tool does.
    
    REQUIRED PARAMETERS:
    - param1 (type): Description of param1 with examples
    - param2 (type): Description of param2 with examples
    
    OPTIONAL PARAMETERS:
    - param3 (type, default=value): Description of param3
    
    EXAMPLES:
    1. Example use case 1: tool_name(param1='value1', param2='value2')
    2. Example use case 2: tool_name(param1='value3', param2={'key': 'value'})
    
    RETURNS:
    - success: Boolean indicating success
    - data: The created/updated/retrieved data
    - display_markdown: User-friendly formatted output
    
    IMPORTANT: [Any critical notes about usage, constraints, or requirements]""",
    category="app_name",
    log_response_to_orm=True
)
async def tool_name(
    param1: str,
    param2: dict,
    param3: Optional[str] = None,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Internal docstring for developers."""
    pass
```

## Key Principles

### 1. Be Explicit About Parameters
❌ Bad: `description="Create a contact"`
✅ Good: 
```
description="""Create a new contact in the system.

REQUIRED PARAMETERS:
- name (str): Full name of the contact (e.g., 'John Doe')
- email (str): Email address (e.g., 'john@example.com')

OPTIONAL PARAMETERS:
- phone (str): Phone number (e.g., '555-1234')
- company (str): Company name
"""
```

### 2. Provide Examples
Always include 1-3 concrete examples showing how to call the tool:

```python
EXAMPLES:
1. Create basic contact: create_contact(name='John Doe', email='john@example.com')
2. Create with phone: create_contact(name='Jane Smith', email='jane@example.com', phone='555-5678')
3. Create with all fields: create_contact(name='Bob Wilson', email='bob@example.com', phone='555-9999', company='Acme Corp')
```

### 3. Specify Data Types Clearly
For complex types (dict, list), show the expected structure:

```python
REQUIRED PARAMETERS:
- details (dict): Contact details with structure:
  {
    'address': 'street address',
    'city': 'city name',
    'state': 'state code',
    'zip': 'postal code'
  }
```

### 4. Document Return Values
Explain what the tool returns:

```python
RETURNS:
- status: 'created' or 'updated'
- contact_id: UUID of the created contact
- display_markdown: Formatted success message
```

### 5. Add Important Notes
Include any critical information:

```python
IMPORTANT: 
- Email must be unique per user
- Phone numbers are stored without formatting
- Do not call with empty dict - all required parameters must be provided
```

## Real-World Examples

### Example 1: CRUD Tool
```python
@agent_tool(
    name="create_client",
    description="""Create a new client record in the legal practice management system.
    
    REQUIRED PARAMETERS:
    - name (str): Full legal name of the client (e.g., 'John Smith')
    - case_type (str): Type of legal case (e.g., 'criminal', 'civil', 'family')
    
    OPTIONAL PARAMETERS:
    - email (str): Client email address
    - phone (str): Contact phone number
    - notes (str): Additional notes about the client
    
    EXAMPLES:
    1. Basic client: create_client(name='John Smith', case_type='criminal')
    2. With contact info: create_client(name='Jane Doe', case_type='civil', email='jane@example.com', phone='555-1234')
    3. Full details: create_client(name='Bob Wilson', case_type='family', email='bob@example.com', phone='555-5678', notes='Referred by partner')
    
    RETURNS:
    - status: 'created'
    - client_id: UUID of the new client
    - display_markdown: Success message with client details
    
    IMPORTANT: case_type must be one of: 'criminal', 'civil', 'family', 'corporate'""",
    category="legal",
    log_response_to_orm=True
)
async def create_client(
    name: str,
    case_type: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Create a new client record."""
    pass
```

### Example 2: Search Tool
```python
@agent_tool(
    name="search_clients",
    description="""Search for clients in the legal practice database.
    
    REQUIRED PARAMETERS:
    - query (str): Search term to match against client names, emails, or case types
    
    OPTIONAL PARAMETERS:
    - case_type (str): Filter by specific case type (e.g., 'criminal', 'civil')
    - limit (int, default=10): Maximum number of results to return
    
    EXAMPLES:
    1. Search by name: search_clients(query='John')
    2. Filter by case type: search_clients(query='Smith', case_type='criminal')
    3. Limit results: search_clients(query='Doe', limit=5)
    
    RETURNS:
    - results: List of matching client records
    - count: Total number of matches
    - display_markdown: Formatted list of clients
    
    IMPORTANT: Search is case-insensitive and matches partial names""",
    category="legal",
    log_response_to_orm=True
)
async def search_clients(
    query: str,
    case_type: Optional[str] = None,
    limit: int = 10,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Search for clients."""
    pass
```

### Example 3: Tool with Complex Parameters
```python
@agent_tool(
    name="log_case_activity",
    description="""Log an activity or event for a legal case.
    
    REQUIRED PARAMETERS:
    - case_id (str): UUID of the case
    - activity_type (str): Type of activity (e.g., 'meeting', 'filing', 'hearing', 'research')
    - details (dict): Activity details with structure:
      {
        'date': 'YYYY-MM-DD',
        'description': 'What happened',
        'duration_minutes': 60,
        'billable': true/false
      }
    
    OPTIONAL PARAMETERS:
    - attachments (list): List of file paths or document IDs
    
    EXAMPLES:
    1. Log meeting: log_case_activity(
         case_id='123e4567-e89b-12d3-a456-426614174000',
         activity_type='meeting',
         details={'date': '2026-02-07', 'description': 'Client consultation', 'duration_minutes': 60, 'billable': true}
       )
    2. Log filing: log_case_activity(
         case_id='123e4567-e89b-12d3-a456-426614174000',
         activity_type='filing',
         details={'date': '2026-02-07', 'description': 'Filed motion to dismiss', 'duration_minutes': 30, 'billable': true},
         attachments=['motion_123.pdf']
       )
    
    RETURNS:
    - status: 'logged'
    - activity_id: UUID of the logged activity
    - display_markdown: Formatted activity summary
    
    IMPORTANT: 
    - date must be in YYYY-MM-DD format
    - duration_minutes must be a positive integer
    - billable must be boolean (true/false)""",
    category="legal",
    log_response_to_orm=True
)
async def log_case_activity(
    case_id: str,
    activity_type: str,
    details: dict,
    attachments: Optional[list] = None,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Log case activity."""
    pass
```

## Common Mistakes to Avoid

### ❌ Mistake 1: Vague Description
```python
description="Store data"  # Too vague!
```

### ✅ Fix:
```python
description="""Store structured contact information.

REQUIRED PARAMETERS:
- name (str): Contact name
- email (str): Email address
...
"""
```

### ❌ Mistake 2: No Parameter Documentation
```python
description="Create a new record"  # What parameters?
```

### ✅ Fix:
```python
description="""Create a new record.

REQUIRED PARAMETERS:
- field1 (str): Description
- field2 (dict): Structure: {'key': 'value'}
...
"""
```

### ❌ Mistake 3: No Examples
```python
description="Search for items"  # How do I use it?
```

### ✅ Fix:
```python
description="""Search for items.

EXAMPLES:
1. search_items(query='laptop')
2. search_items(query='phone', category='electronics')
...
"""
```

## Validation Checklist

Before generating a tool, ensure:
- [ ] One-line summary at the top
- [ ] REQUIRED PARAMETERS section with types and examples
- [ ] OPTIONAL PARAMETERS section (if any)
- [ ] EXAMPLES section with 1-3 concrete examples
- [ ] RETURNS section explaining output structure
- [ ] IMPORTANT section with critical notes
- [ ] All complex types (dict, list) show expected structure
- [ ] Examples use realistic values, not placeholders
