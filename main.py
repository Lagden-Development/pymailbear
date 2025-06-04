import uvicorn
import os
import logging
from app.api import app

if __name__ == "__main__":
    # Get port from environment or default to 1234
    port = int(os.environ.get("PORT", 1234))

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=port)
