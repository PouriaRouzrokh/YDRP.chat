# # In mcp_server/tools/add_policy.py
# @mcp.tool()
# async def add_policy(url: str, follow_links: bool = False, depth: int = 1) -> str:
#     """Add a new policy from a URL to the system.
    
#     Args:
#         url: URL of the policy to add
#         follow_links: Whether to follow links from the provided URL
#         depth: How many levels deep to follow links
#     """
#     from ydrpolicy.backend.services.policy_processor import PolicyProcessorService
#     from ydrpolicy.backend.database.repository.policies import PolicyRepository
    
#     async with get_async_session() as session:
#         policy_repo = PolicyRepository(session)
#         processor = PolicyProcessorService(policy_repo, session)
        
#         try:
#             policy = await processor.process_url(url, follow_links=follow_links, depth=depth)
#             return f"Successfully added policy: {policy.title} (ID: {policy.id})"
#         except Exception as e:
#             return f"Error adding policy: {str(e)}"