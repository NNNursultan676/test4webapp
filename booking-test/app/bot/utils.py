from aiogram import Bot
from aiogram.types import ChatMember
from config import ADMIN_IDS, GROUP_ID

async def get_user_role(bot: Bot, user_id: int) -> str:
    """Returns the role of the user in the group."""
    if user_id in ADMIN_IDS:
        return "admin"  # If the user is in the admin list, return 'admin'
    
    try:
        member: ChatMember = await bot.get_chat_member(GROUP_ID, user_id)

        # Check user status and return appropriate role
        if member.status == "creator":
            return "owner"  # If the user is the group creator, return 'owner'
        elif member.status == "administrator":
            return "admin"  # If the user is an admin
        elif member.status == "member":
            return "member"  # If the user is a regular member
        else:
            return "unknown"  # In case of other statuses like 'left' or 'kicked'

    except Exception as e:
        print(f"Error checking user status in the group: {e}")
        return "unknown"  # Return 'unknown' if there was an error

# Usage example
async def is_user_admin(bot: Bot, user_id: int) -> bool:
    """Returns True if the user is an admin (admin or owner), False if not."""
    role = await get_user_role(bot, user_id)
    return role in ["admin", "owner"]
