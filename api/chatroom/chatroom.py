from core.database.models import (Chatrooms, Apps, ChatroomAgentRelation, ChatroomMessages)
from fastapi import APIRouter
from api.utils.common import *
from api.utils.jwt import *
from api.schema.chat import *
from languages import get_language_content
router = APIRouter()


@router.get("/", response_model=ChatRoomListResponse, summary="Fetching the List of Chat Rooms")
async def chatroom_list(page: int = 1, page_size: int = 10, name: str = "", userinfo: TokenData = Depends(get_current_user)):
    """
    Fetch a list of all chat rooms.

    This endpoint fetches a paginated list of all available chat rooms, allowing users to optionally filter the results by a name. The pagination is controlled through the page number and page size parameters.

    Parameters:
    - page (int): The current page number for pagination. Defaults to 1.
    - page_size (int): The number of chat rooms to return per page. Defaults to 10.
    - name (str): Optional. A string to filter chat rooms by name.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A successful response containing the list of chat rooms, formatted according to the ChatRoomListResponse model.

    Raises:
    - HTTPException: If there are issues with pagination parameters or if the user is not authenticated.
    """
    result = Chatrooms().all_chat_room_list(page, page_size, userinfo.uid, name)
    return response_success(result)


@router.post("/", response_model=CreateChatRoomResponse, summary="Create a new Chat Room")
async def create_chatroom(chat_request: ReqChatroomCreateSchema, userinfo: TokenData = Depends(get_current_user)):
    """
    Create a new chat room with specified attributes.

    This endpoint facilitates the creation of a chat room, allowing configuration of various settings such as name, description, API access, visibility, and activation status through the provided schema. The mode parameter specifies the type of application, with a default value for chat rooms.

    Parameters:
    - chat_request (ReqChatroomCreateSchema): A schema containing all the necessary information to create a chat room, including name, description, API access settings, visibility, and activation status. Required.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object indicating the success of the operation and containing the ID of the created chat room, formatted according to the CreateChatRoomResponse model.

    Raises:
    - HTTPException: If any of the required parameters are missing or invalid, or if the user is not authenticated.
    """
    chat_data = chat_request.dict(exclude_unset=True)
    name: str = chat_data['name']
    description: str = chat_data['description']
    max_round: int = chat_data['max_round']
    agent = chat_data['agent']
    mode: int = 5

    if not name:
        return response_error(get_language_content("chatroom_name_is_required"))

    if max_round is None or max_round == '':
        return response_error(get_language_content("chatroom_max_round_is_required"))

    if not agent or len(agent) == 0:
        return response_error(get_language_content("chatroom_agent_is_required"))
    else:
        required_keys = {'agent_id', 'active'}
        for index, item in enumerate(agent):
            if not isinstance(item, dict):
                return response_error(get_language_content("chatroom_agent_item_must_be_a_dictionary"))

            missing_keys = required_keys - item.keys()
            if missing_keys:
                return response_error(get_language_content("chatroom_agent_item_missing_keys"))

    app_id = Apps().insert(
        {
            'team_id': userinfo.team_id,
            'user_id': userinfo.uid,
            'name': name,
            'description': description,
            'mode': mode,
            'status': 1
        }
    )
    chatroom_id = Chatrooms().insert(
        {
            'team_id': userinfo.team_id,
            'user_id': userinfo.uid,
            'app_id': app_id,
            'max_round': max_round,
            'status': 1
        }
    )
    ChatroomAgentRelation().insert_agent(
        {
            'agent': agent,
            'chatroom_id': chatroom_id
        }
    )

    return response_success({'chatroom_id': chatroom_id})


@router.get("/recent", response_model=RecentChatRoomListResponse, summary="Fetch a List of Recently Accessed Chat Rooms")
async def recent_chatroom_list(chatroom_id: int, userinfo: TokenData = Depends(get_current_user)):
    """
    Fetch a list of chat rooms that the user has recently accessed.

    This endpoint retrieves a list of chat rooms sorted by the time of the user's last access, providing an easy way to access frequently used chat rooms.
    The list excludes the chat room with the specified chatroom_id.

    Parameters:
    - chatroom_id (int): The ID of the chat room to exclude from the recently accessed list. This could be used to exclude the current chat room from the list of recent chat rooms.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object containing the list of recently accessed chat rooms, formatted according to the RecentChatRoomListResponse model.

    Raises:
    - HTTPException: If the user is not authenticated or if there are other issues with the request.
    """
    result = Chatrooms().recent_chatroom_list(chatroom_id, userinfo.uid)
    return response_success(result)


@router.delete("/{chatroom_id}", response_model=OperationResponse, summary="Delete the Chat Room")
async def delete_chatroom(chatroom_id: int, userinfo: TokenData = Depends(get_current_user)):
    """
    Delete a chat room by its ID.

    This endpoint allows users to delete a chat room based on the provided chat room ID. The deletion process involves setting the status of the chat room and associated app to an inactive state, rather than physically removing the data.

    Parameters:
    - chatroom_id (int): The unique identifier of the chat room to be deleted. Required.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Raises:
    - HTTPException: If the chat room ID is missing, the user is not authenticated, or the chat room does not exist.
    """
    if not chatroom_id:
        return response_error(get_language_content("chatroom_id_is_required"))

    find_chatroom = Chatrooms().search_chatrooms_id(chatroom_id, userinfo.uid)
    if not find_chatroom['status']:
        return response_error(get_language_content("chatroom_does_not_exist"))

    Chatrooms().update(
        [
            {"column": "id", "value": chatroom_id},
            {"column": "user_id", "value": userinfo.uid},
        ], {
            'status': 3
        }
    )
    Apps().update(
        [
            {"column": "user_id", "value": userinfo.uid},
            {"column": "id", "value": find_chatroom['app_id']},
        ], {
            'status': 3
        }
    )
    ChatroomAgentRelation().delete(
        [
            {"column": "chatroom_id", "value": chatroom_id},
        ]
    )
    return response_success({'msg': get_language_content("chatroom_delete_success")})


@router.get("/{chatroom_id}/details", response_model=ChatRoomDetailResponse, summary="Fetching Details of a Chat Room")
async def show_chatroom_details(chatroom_id: int, userinfo: TokenData = Depends(get_current_user)):
    """
    Fetch detailed information about a specific chat room.

    This endpoint fetches comprehensive details about a chat room, including associated application data and the list of agents that have joined the chat room. It serves users who need to view the configuration and participants of a chat room.

    Parameters:
    - chatroom_id (int): The unique identifier of the chat room to fetch details for. Required.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object that contains chat room details and a list of joined agents, and records the current number of my agents and the number of agents in the team, formatted according to the ChatRoomDetailResponse model.

    Raises:
    - HTTPException: If the 'chatroom_id' is invalid, the user is not authenticated, or the chat room does not exist.
    """
    find_chatroom = Chatrooms().search_chatrooms_id(chatroom_id, userinfo.uid)
    if not find_chatroom['status']:
        return response_success(
            detail=get_language_content("chatroom_does_not_exist"),
            code=1
        )

    chat_info = Apps().get_app_by_id(find_chatroom['app_id'])
    agent_list = ChatroomAgentRelation().show_chatroom_agent(chatroom_id)

    for agent in agent_list:
        agent['type'] = ''
        if agent['user_id'] == userinfo.uid:
            agent['type'] = 'my_agent'
        else:
            agent['type'] = 'more_agent'

    return response_success({
        'chat_info': chat_info,
        'agent_list': agent_list,
        'max_round': find_chatroom['max_round'],
        'smart_selection': find_chatroom['smart_selection'],
        'chatroom_status': find_chatroom['chatroom_status']
    })


@router.post("/{chatroom_id}/smart_selection", response_model=ChatRoomResponseBase, summary="Enables or Disables Smart Selection for a Chat Room")
async def toggle_smart_selection_switch(chatroom_id: int, data: ToggleSmartSelectionSwitch, userinfo: TokenData = Depends(get_current_user)):
    """
    Enables or Disables Smart Selection for a Chat Room.

    This endpoint allows the modification of the smart selection status of a chat room.
    It sets the smart selection status of the specified chat room based on the provided value.

    Parameters:
    - chatroom_id (int): The unique identifier of the chat room. Required.
    - data (ToggleSmartSelectionSwitch): A data model containing the new smart selection status for the chat room. Required.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object indicating the success of the operation, formatted according to the ChatRoomResponseBase model.

    Raises:
    - HTTPException: If the 'chatroom_id' is invalid, the user is not authenticated, or the chat room does not exist.
    - HTTPException: If the 'smart_selection' value is not provided or is not one of the accepted values (0 or 1).
    """

    if not chatroom_id:
        return response_error(get_language_content("chatroom_id_is_required"))

    find_chatroom = Chatrooms().search_chatrooms_id(chatroom_id, userinfo.uid)
    if not find_chatroom['status']:
        return response_error(get_language_content("chatroom_does_not_exist"))

    if data.smart_selection is None or data.smart_selection == '':
        return response_error(get_language_content("chatroom_smart_selection_status_is_required"))

    if data.smart_selection not in [0, 1]:
        return response_error(get_language_content("chatroom_smart_selection_status_can_only_input"))

    Chatrooms().update(
        {'column': 'id', 'value': chatroom_id},
        {'smart_selection': data.smart_selection}
    )

    return response_success()


@router.post("/{chatroom_id}/update_chatroom", response_model=UpdateChatRoomResponse, summary="Update the Chat Room")
async def update_chatroom(chatroom_id: int, chat_request: ReqChatroomUpdateSchema, userinfo: TokenData = Depends(get_current_user)):
    """
    Updates an existing chat room with specified attributes.

    This endpoint allows for the modification of various chat room settings, including name, description, API access, visibility, and activation status.
    The chat room's mode is set to a default value, and the provided information is used to update the chat room's configuration.

    Parameters:
    - chatroom_id (int): The unique identifier of the chat room to be updated. Required.
    - chat_request (ReqChatroomUpdateSchema): A schema containing all the information required to update the chat room, including name, description, API access settings, visibility, and activation status. Compulsory.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object representing a successful operation and containing the updated chat room ID, formatted according to the UpdateChatRoomResponse model.

    Raises:
    - HTTPException: If any required parameters are missing or invalid, or if the user has not been authenticated.
    """
    chat_data = chat_request.dict(exclude_unset=True)
    name: str = chat_data['name']
    description: str = chat_data['description']
    max_round: int = chat_data['max_round']
    # agent = chat_data['agent']
    new_agents: List[AgentModel] = chat_data['agent']
    mode: int = 5
    find_chatroom = Chatrooms().search_chatrooms_id(chatroom_id, userinfo.uid)
    if not find_chatroom['status']:
        return response_error(get_language_content("chatroom_does_not_exist"))

    if not name:
        return response_error(get_language_content("chatroom_name_is_required"))

    if max_round is None or max_round == '':
        return response_error(get_language_content("chatroom_max_round_is_required"))

    if not new_agents or len(new_agents) == 0:
        return response_error(get_language_content("chatroom_agent_is_required"))
    else:
        required_keys = {'agent_id', 'active'}
        for index, item in enumerate(new_agents):
            if not isinstance(item, dict):
                return response_error(get_language_content("chatroom_agent_item_must_be_a_dictionary"))

            missing_keys = required_keys - item.keys()
            if missing_keys:
                return response_error(get_language_content("chatroom_agent_item_missing_keys"))

    Apps().update(
        [
            {"column": "id", "value": find_chatroom['app_id']},
            {"column": "team_id", "value": userinfo.team_id},
            {"column": "user_id", "value": userinfo.uid},
            {"column": "mode", "value": 5},
        ], {
            'name': name,
            'description': description
        }
    )

    Chatrooms().update(
        [
            {"column": "id", "value": chatroom_id}
        ], {
            'max_round': max_round
        }
    )

    existing_agents = ChatroomAgentRelation().get_agents_by_chatroom_id(chatroom_id)

    existing_agent_ids = {agent['agent_id'] for agent in existing_agents}

    new_agent_ids = {agent['agent_id'] for agent in new_agents}
    agents_to_delete = existing_agent_ids - new_agent_ids
    agents_to_add = [agent for agent in new_agents if agent['agent_id'] not in existing_agent_ids]
    agents_to_update = [agent for agent in new_agents if agent['agent_id'] in existing_agent_ids]

    if agents_to_delete:
        agent_ids = list(agents_to_delete)
        for agent_id in agent_ids:
            ChatroomAgentRelation().delete(
                [
                    {"column": "agent_id", "value": agent_id},
                    {"column": "chatroom_id", "value": chatroom_id},
                ]
            )

    if agents_to_add:
        ChatroomAgentRelation().insert_agent(
            {
                'agent': agents_to_add,
                'chatroom_id': chatroom_id
            }
        )

    if agents_to_update:
        ChatroomAgentRelation().insert_agent(
            {
                'agent': agents_to_update,
                'chatroom_id': chatroom_id
            }
        )


    return response_success({'chatroom_id': chatroom_id})


@router.put("/{chatroom_id}/agents/{agent_id}/setting", response_model=ChatRoomResponseBase, summary="Set the Chat Room Agent's Automatic Responses")
async def toggle_auto_answer_switch(chatroom_id: int, agent_id: int, agent_setting: ReqAgentSettingSchema, userinfo: TokenData = Depends(get_current_user)):
    """
    Set the automatic response settings for an agent in a chat room.

    This endpoint allows the modification of an agent's automatic response behavior within a chat room. It enables the setting of whether the automatic response feature is active and the frequency of automatic replies.

    Parameters:
    - chatroom_id (int): The unique identifier of the chat room where the agent's settings are to be modified. Required.
    - agent_id (int): The unique identifier of the agent whose settings are being updated. Required.
    - agent_setting (ReqAgentSettingSchema): A schema containing the settings for the agent, including whether the automatic response feature is enabled and the number of automatic responses. Required.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object indicating the success of the operation, formatted according to the ChatRoomResponseBase model.

    Raises:
    - HTTPException: If the 'chatroom_id' or 'agent_id' is invalid, the user is not authenticated, or the chat room or agent does not exist.
    """
    if not chatroom_id:
        return response_error(get_language_content("chatroom_id_is_required"))

    find_chatroom = Chatrooms().search_chatrooms_id(chatroom_id, userinfo.uid)
    if not find_chatroom['status']:
        return response_error(get_language_content("chatroom_does_not_exist"))

    if not agent_id:
        return response_error(get_language_content("chatroom_agent_id_is_required"))

    find_agent = Chatrooms().search_agent_id(agent_id)
    if not find_agent:
        return response_error(get_language_content("agent_does_not_exist"))

    agent_data = agent_setting.dict(exclude_unset=True)
    active = agent_data['active']

    if active is None or active == '':
        return response_error(get_language_content("chatroom_agent_active_is_required"))

    if active not in [0, 1]:
        return response_error(get_language_content("chatroom_agent_active_can_only_input"))

    find_chatroom_agent = ChatroomAgentRelation().search_chatroom_agent_relation_id(chatroom_id, agent_id)
    if not find_chatroom_agent['status']:
        return response_error(get_language_content("chatroom_agent_relation_does_not_exist"))
    
    if active == 0:
        agents = ChatroomAgentRelation().get_active_agents_by_chatroom_id(chatroom_id)
        if len(agents) <= 1:
            return response_error(get_language_content("chatroom_agent_number_less_than_one"))

    ChatroomAgentRelation().update(
        [
            {"column": "chatroom_id", "value": chatroom_id},
            {"column": "agent_id", "value": agent_id},
        ], {
            'active': active
        }
    )
    return response_success()


@router.get("/{chatroom_id}/chatroom_message", response_model=ChatRoomResponseBase, summary="Get a list of historical messages")
async def show_chatroom_details(chatroom_id: int, page: int = 1, page_size: int = 10, userinfo: TokenData = Depends(get_current_user)):
    """
    Retrieve historical messages for a specific chat room.

    This endpoint retrieves historical chat information about the chat room and provides services for users who need to view chat history and participants.

    Parameters:
    - chatroom_id (int): The unique identifier of the chat room to fetch details for. Required.
    - userinfo (TokenData): Information about the current user, provided through dependency injection. Required.

    Returns:
    - A response object containing the chat room details and the list of joined agents, formatted according to the HistoryChatroomMessages model.

    Raises:
    - HTTPException: If the 'chatroom_id' is invalid, the user is not authenticated, or the chat room does not exist.
    """
    find_chatroom = Chatrooms().search_chatrooms_id(chatroom_id, userinfo.uid)
    if not find_chatroom['status']:
        return response_error(get_language_content("chatroom_does_not_exist"))

    chatroom_history_msg = ChatroomMessages().history_chatroom_messages(chatroom_id, page, page_size)

    Chatrooms().update(
        {"column": "id", "value": chatroom_id},
        {'active': 0}
    )
    ChatroomMessages().update(
        {"column": "chatroom_id", "value": chatroom_id},
        {'is_read': 1}
    )

    return response_success(chatroom_history_msg)