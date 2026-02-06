"""
Research Agent - Finds APIs, libraries, and patterns for any domain.

Uses web search and browsing to discover relevant resources.
"""
import logging
from typing import Optional
from pydantic import BaseModel, Field
from agents.schemas import DomainSpec
from agents.model_router import model_router

logger = logging.getLogger(__name__)


class ResearchResult(BaseModel):
    """Result from research agent."""
    domain: str
    apis_found: list[dict] = Field(default_factory=list)
    libraries_found: list[dict] = Field(default_factory=list)
    patterns_found: list[str] = Field(default_factory=list)
    pip_dependencies: list[str] = Field(default_factory=list)
    code_examples: list[str] = Field(default_factory=list)
    recommendations: str = ""


class ResearchAgent:
    """
    Research agent that finds APIs, libraries, and patterns for any domain.
    
    Uses the web_research tools to gather information.
    """
    
    async def research(self, domain_spec: DomainSpec) -> ResearchResult:
        """
        Research a domain and find relevant APIs, libraries, and patterns.
        
        Args:
            domain_spec: Domain specification from analyzer
            
        Returns:
            ResearchResult with found resources
        """
        logger.info(f"Researching domain: {domain_spec.domain_name}")
        
        apis_found = []
        libraries_found = []
        patterns_found = []
        pip_dependencies = []
        
        # Search for each query
        for query in domain_spec.search_queries[:3]:  # Limit to 3 queries
            try:
                result = await self._search(query)
                
                # Extract APIs from results
                apis = self._extract_apis(result)
                apis_found.extend(apis)
                
                # Extract libraries
                libs = self._extract_libraries(result)
                libraries_found.extend(libs)
                
            except Exception as e:
                logger.warning(f"Search failed for '{query}': {e}")
        
        # Deduplicate
        apis_found = self._deduplicate(apis_found)
        libraries_found = self._deduplicate(libraries_found)
        
        # Extract pip dependencies from libraries
        for lib in libraries_found:
            if lib.get("pip_name"):
                pip_dependencies.append(lib["pip_name"])
        
        # Generate recommendations using LLM
        recommendations = await self._generate_recommendations(
            domain_spec, apis_found, libraries_found
        )
        
        return ResearchResult(
            domain=domain_spec.domain_name,
            apis_found=apis_found,
            libraries_found=libraries_found,
            patterns_found=patterns_found,
            pip_dependencies=pip_dependencies,
            recommendations=recommendations
        )
    
    async def _search(self, query: str) -> dict:
        """Execute a web search."""
        from core.registry import capability_registry
        
        search_tool = capability_registry.get_tool("search_web")
        if search_tool:
            try:
                result = await search_tool(query=query, max_results=5)
                return result
            except Exception as e:
                logger.warning(f"Search tool failed: {e}")
        
        # Fallback: return empty result
        return {"results": []}
    
    def _extract_apis(self, search_result: dict) -> list[dict]:
        """Extract API references from search results."""
        apis = []
        
        for result in search_result.get("results", []):
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            url = result.get("url", "")
            
            # Look for API indicators
            if any(keyword in title + snippet for keyword in ["api", "rest", "graphql", "endpoint"]):
                apis.append({
                    "name": result.get("title", "Unknown API"),
                    "url": url,
                    "description": result.get("snippet", "")[:200]
                })
        
        return apis
    
    def _extract_libraries(self, search_result: dict) -> list[dict]:
        """Extract library references from search results."""
        libraries = []
        
        for result in search_result.get("results", []):
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            url = result.get("url", "")
            
            # Look for library indicators
            if any(keyword in title + snippet for keyword in ["library", "package", "pip install", "pypi"]):
                # Try to extract pip name
                pip_name = None
                if "pip install" in snippet:
                    parts = snippet.split("pip install")
                    if len(parts) > 1:
                        pip_name = parts[1].strip().split()[0] if parts[1].strip() else None
                
                libraries.append({
                    "name": result.get("title", "Unknown Library"),
                    "url": url,
                    "pip_name": pip_name,
                    "description": result.get("snippet", "")[:200]
                })
        
        return libraries
    
    def _deduplicate(self, items: list[dict]) -> list[dict]:
        """Remove duplicate items based on URL."""
        seen_urls = set()
        unique = []
        
        for item in items:
            url = item.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique.append(item)
        
        return unique
    
    async def _generate_recommendations(
        self,
        domain_spec: DomainSpec,
        apis: list[dict],
        libraries: list[dict]
    ) -> str:
        """Generate recommendations using LLM."""
        try:
            response = await model_router.complete(
                task_type="summarize",
                messages=[{
                    "role": "user",
                    "content": f"""Based on research for {domain_spec.domain_name} domain:
                    
APIs found: {[a['name'] for a in apis[:5]]}
Libraries found: {[l['name'] for l in libraries[:5]]}

Provide a brief recommendation (2-3 sentences) on which tools to prioritize for building a {domain_spec.domain_name} management app."""
                }],
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Recommendation generation failed: {e}")
            return "Use standard Django patterns with the discovered APIs."


# Singleton instance
research_agent = ResearchAgent()
