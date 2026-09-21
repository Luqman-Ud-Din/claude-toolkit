from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent

llm = ChatAnthropic(model="claude-sonnet-4-5")
# agent wired up with tools elsewhere in this file
