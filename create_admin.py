import asyncio
import getpass
import secrets
import hashlib
import bcrypt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database.models import User
from app.config import get_config
from app.database.connection import get_database_url


async def create_admin():
    """Create an admin user."""
    print("Creating admin user...")

    # Get config and database URL
    config = get_config()
    database_url = get_database_url(config)

    # Create async engine
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Get admin credentials
    email = input("Admin email: ")
    name = input("Admin name: ")
    password = getpass.getpass("Admin password: ")

    # Hash password
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Create user
    async with async_session() as session:
        async with session.begin():
            # Check if admin already exists
            from sqlalchemy import select

            query = select(User).where(User.email == email)
            result = await session.execute(query)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"User with email {email} already exists.")
                return

            # Create new admin user
            user = User(
                email=email, name=name, password_hash=hashed_password, role="admin"
            )
            session.add(user)

        await session.commit()

    print(f"Admin user {email} created successfully!")


if __name__ == "__main__":
    asyncio.run(create_admin())
