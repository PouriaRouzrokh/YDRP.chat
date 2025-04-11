# # In backend/routers/policies.py
# @router.post("/policies/add")
# async def add_policy(
#     request: AddPolicyRequest,
#     current_user: User = Depends(get_current_admin_user),
#     session: AsyncSession = Depends(get_session)
# ):
#     """Add a new policy from a URL."""
#     policy_repo = PolicyRepository(session)
#     processor = PolicyProcessorService(policy_repo, session)
    
#     policy = await processor.process_url(
#         url=request.url,
#         admin_id=current_user.id,
#         follow_links=request.follow_links,
#         depth=request.depth
#     )
    
#     return {"message": "Policy added successfully", "policy": policy}