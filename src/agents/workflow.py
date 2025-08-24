from agents import Runner
from test_generator.test_generator_agent import TEST_GENERATOR_AGENT
from repo_scanner.repo_scanner_agent import REPO_SCANNER_AGENT
from dotenv import load_dotenv
import os
import json

# Run the agent with a sample input
async def main():
    load_dotenv()  # Load environment variables from .env file
    repo = "shankar0909/springboot-rest-demo"
    print("****************************************************** SCANNER AGENT PROCESSING STARTED  ******************************************************")
    a1Result = await Runner.run(REPO_SCANNER_AGENT, repo)
    print(a1Result.final_output)
    print("****************************************************** SCANNER AGENT PROCESSING FINISHED ******************************************************")
    print("****************************************************** GENERATOR AGENT PROCESSING STARTED ******************************************************")
    a2Result = await Runner.run(TEST_GENERATOR_AGENT, a1Result.final_output)
    print(a2Result)
    print("****************************************************** GENERATOR AGENT PROCESSING FINISHED ******************************************************")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
       