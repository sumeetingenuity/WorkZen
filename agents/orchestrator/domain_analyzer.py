"""
Domain Analyzer - Extracts domain requirements from natural language.

Uses LLM to understand user's domain and generate structured specs.
"""
import logging
from typing import Optional
from agents.schemas import DomainSpec, AppSpec, EntitySpec, ToolSpec, FieldSpec, FieldType
from agents.model_router import model_router

logger = logging.getLogger(__name__)


# Domain patterns for common use cases
DOMAIN_PATTERNS = {
    "legal": {
        "keywords": ["lawyer", "legal", "attorney", "law firm", "case", "court"],
        "entities": ["Client", "Case", "Document", "Contract", "CourtDate", "Invoice"],
        "workflows": ["case_intake", "document_review", "contract_generation", "court_reminder"],
        "integrations": ["google_calendar", "email", "docusign"],
        "search_queries": [
            "legal practice management API",
            "court calendar API",
            "contract generation library python",
            "DocuSign API integration Django",
        ]
    },
    "healthcare": {
        "keywords": ["doctor", "clinic", "hospital", "patient", "medical", "healthcare"],
        "entities": ["Patient", "Appointment", "MedicalRecord", "Prescription", "Staff"],
        "workflows": ["appointment_booking", "prescription_renewal", "lab_results"],
        "integrations": ["google_calendar", "sms", "email"],
        "search_queries": [
            "healthcare scheduling API",
            "HIPAA compliant storage python",
            "electronic health records API",
        ]
    },
    "real_estate": {
        "keywords": ["realtor", "real estate", "property", "house", "rental"],
        "entities": ["Property", "Client", "Listing", "Showing", "Contract", "Transaction"],
        "workflows": ["listing_creation", "showing_schedule", "contract_generation"],
        "integrations": ["zillow_api", "google_maps", "email"],
        "search_queries": [
            "real estate listing API",
            "property search API python",
            "MLS integration API",
        ]
    },
    "finance": {
        "keywords": ["accountant", "finance", "tax", "bookkeeping", "invoice"],
        "entities": ["Client", "Invoice", "Expense", "Transaction", "Report", "TaxDocument"],
        "workflows": ["invoice_generation", "expense_tracking", "tax_preparation"],
        "integrations": ["quickbooks", "stripe", "email"],
        "search_queries": [
            "QuickBooks API python",
            "invoice generation library",
            "tax calculation API",
        ]
    },
}


class DomainAnalyzer:
    """
    Analyzes user's domain description and extracts structured requirements.
    """
    
    async def analyze(self, user_description: str) -> DomainSpec:
        """
        Analyze user description and return domain specification.
        
        Input: "I'm a lawyer managing cases and clients"
        Output: DomainSpec with entities, workflows, integrations
        """
        logger.info(f"Analyzing domain: {user_description[:100]}")
        
        # First try pattern matching for common domains
        domain = self._match_known_domain(user_description)
        
        if domain:
            pattern = DOMAIN_PATTERNS[domain]
            return DomainSpec(
                domain_name=domain,
                key_entities=pattern["entities"],
                key_workflows=pattern["workflows"],
                suggested_integrations=pattern["integrations"],
                search_queries=pattern["search_queries"]
            )
        
        # For unknown domains, use LLM
        return await self._analyze_with_llm(user_description)
    
    def _match_known_domain(self, description: str) -> Optional[str]:
        """Try to match description to known domain patterns."""
        description_lower = description.lower()
        
        for domain, pattern in DOMAIN_PATTERNS.items():
            for keyword in pattern["keywords"]:
                if keyword in description_lower:
                    logger.info(f"Matched domain: {domain}")
                    return domain
        
        return None
    
    async def _analyze_with_llm(self, description: str) -> DomainSpec:
        """Use LLM to analyze unknown domain."""
        try:
            result = await model_router.complete(
                task_type="orchestrate",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a domain analyzer. Given a user's description of their profession or business,
                        extract the key information needed to build a management application.
                        
                        Respond with JSON containing:
                        - domain_name: short identifier (snake_case)
                        - key_entities: list of main data entities they need to manage
                        - key_workflows: list of common workflows in this domain
                        - suggested_integrations: useful external services
                        - search_queries: queries to find relevant APIs/libraries"""
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this domain: {description}"
                    }
                ],
                response_model=DomainSpec
            )
            return result
        except Exception as e:
            logger.error(f"LLM domain analysis failed: {e}")
            # Return a generic domain spec
            return DomainSpec(
                domain_name="custom",
                key_entities=["Client", "Project", "Task", "Document"],
                key_workflows=["task_management", "document_storage"],
                suggested_integrations=["email", "calendar"],
                search_queries=["Django CRM template", "project management API"]
            )
    
    async def create_app_spec(
        self, 
        domain_spec: DomainSpec,
        research_results: Optional[dict] = None
    ) -> AppSpec:
        """
        Create a complete AppSpec from domain analysis and research results.
        """
        app_name = domain_spec.domain_name.replace(" ", "_").lower()
        
        # Generate entities
        entities = []
        for entity_name in domain_spec.key_entities:
            entity = self._generate_entity_spec(entity_name)
            entities.append(entity)
        
        # Generate tools for each entity
        tools = []
        for entity in entities:
            entity_tools = self._generate_entity_tools(entity)
            tools.extend(entity_tools)
        
        # Add workflow tools
        for workflow in domain_spec.key_workflows:
            tool = ToolSpec(
                name=workflow,
                description=f"Execute {workflow.replace('_', ' ')} workflow",
                entity="Workflow",
                operation="custom"
            )
            tools.append(tool)
        
        return AppSpec(
            name=app_name,
            display_name=domain_spec.domain_name.replace("_", " ").title() + " Manager",
            description=f"Domain-specific application for {domain_spec.domain_name}",
            entities=entities,
            tools=tools,
            pip_dependencies=self._get_dependencies(research_results)
        )
    
    def _generate_entity_spec(self, entity_name: str) -> EntitySpec:
        """Generate entity specification with common fields."""
        # Common fields for most entities
        common_fields = {
            "Client": [
                FieldSpec(name="name", field_type=FieldType.STRING, max_length=200),
                FieldSpec(name="email", field_type=FieldType.EMAIL, required=False),
                FieldSpec(name="phone", field_type=FieldType.STRING, max_length=20, required=False),
                FieldSpec(name="address", field_type=FieldType.TEXT, required=False),
                FieldSpec(name="notes", field_type=FieldType.TEXT, required=False),
            ],
            "Case": [
                FieldSpec(name="title", field_type=FieldType.STRING, max_length=300),
                FieldSpec(name="description", field_type=FieldType.TEXT, required=False),
                FieldSpec(name="status", field_type=FieldType.STRING, max_length=50, 
                         choices=[("open", "Open"), ("in_progress", "In Progress"), ("closed", "Closed")]),
                FieldSpec(name="client", field_type=FieldType.FOREIGN_KEY, related_model="Client"),
                FieldSpec(name="court_date", field_type=FieldType.DATETIME, required=False),
            ],
            "Document": [
                FieldSpec(name="title", field_type=FieldType.STRING, max_length=300),
                FieldSpec(name="file", field_type=FieldType.FILE),
                FieldSpec(name="document_type", field_type=FieldType.STRING, max_length=50),
                FieldSpec(name="notes", field_type=FieldType.TEXT, required=False),
            ],
            "Contract": [
                FieldSpec(name="title", field_type=FieldType.STRING, max_length=300),
                FieldSpec(name="template", field_type=FieldType.TEXT, required=False),
                FieldSpec(name="generated_text", field_type=FieldType.TEXT, required=False),
                FieldSpec(name="signed", field_type=FieldType.BOOLEAN, default="False"),
                FieldSpec(name="signed_at", field_type=FieldType.DATETIME, required=False),
            ],
        }
        
        # Get predefined fields or generate generic ones
        fields = common_fields.get(entity_name, [
            FieldSpec(name="name", field_type=FieldType.STRING, max_length=200),
            FieldSpec(name="description", field_type=FieldType.TEXT, required=False),
            FieldSpec(name="status", field_type=FieldType.STRING, max_length=50, required=False),
        ])
        
        return EntitySpec(
            name=entity_name,
            description=f"{entity_name} entity for domain management",
            fields=fields,
            include_timestamps=True,
            include_uuid=True
        )
    
    def _generate_entity_tools(self, entity: EntitySpec) -> list[ToolSpec]:
        """Generate CRUD tools for an entity."""
        entity_lower = entity.name.lower()
        
        return [
            ToolSpec(
                name=f"create_{entity_lower}",
                description=f"Create a new {entity.name}",
                entity=entity.name,
                operation="create"
            ),
            ToolSpec(
                name=f"get_{entity_lower}",
                description=f"Get {entity.name} by ID",
                entity=entity.name,
                operation="read"
            ),
            ToolSpec(
                name=f"search_{entity_lower}s",
                description=f"Search {entity.name}s by criteria",
                entity=entity.name,
                operation="search"
            ),
            ToolSpec(
                name=f"update_{entity_lower}",
                description=f"Update an existing {entity.name}",
                entity=entity.name,
                operation="update"
            ),
            ToolSpec(
                name=f"delete_{entity_lower}",
                description=f"Delete a {entity.name}",
                entity=entity.name,
                operation="delete",
                requires_approval=True  # Deletion requires approval
            ),
        ]
    
    def _get_dependencies(self, research_results: Optional[dict]) -> list[str]:
        """Extract pip dependencies from research results."""
        if not research_results:
            return []
        
        return research_results.get("pip_dependencies", [])
