import json
from openai import OpenAI


# 1. Define a tool function with clear type hints and docstring
# The library automatically parses this into the correct JSON tool schema.
def calculate_shipping_cost(destination: str, weight_kg: float) -> str:
    """
    Calculates the shipping cost for a package based on destination and weight.
    
    Args:
        destination: The city or country name.
        weight_kg: The weight of the package in kilograms.
    """
    base_rate = 10.0 if destination.lower() == "hamburg" else 25.0
    total = base_rate + (weight_kg * 1.5)
    return f"${total:.2f}"

def run_streaming_session():
    # Use a reasoning model that natively supports tool calling (e.g., qwen3, deepseek-r1, llama3.1)
    model_name = "gemma4:26b" 
    
    messages = [
        {
            "role": "user", 
            "content": "I need to ship a 5kg box to Hamburg. Can you check the price and tell me why it costs that much?"
        }
    ]

    print(f"--- Sending request to {model_name} (Streaming Enabled) ---")

    shipping_tool = {
        "type": "function",
        "function": {
            "name": "calculate_shipping_cost",
            "description": "Calculates the shipping cost for a package based on destination and weight.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "The city or country name."
                    },
                    "weight_kg": {
                        "type": "number",
                        "description": "The weight of the package in kilograms."
                    }
                },
                "required": ["destination", "weight_kg"]
            }
        }
    }


    client = OpenAI(base_url='http://localhost:11434/v1/', api_key='ollama')
    stream = client.chat.completions.create(    
        model = model_name,
        messages = messages, 
        stream_options = {"include_usage": True}, 
        stream = True,
        reasoning_effort = "low",
        tools = [shipping_tool],
    )
    # Placeholders to assemble everything in chunks
    collected_reasoning = []
    collected_content = []
    tool_calls_buffer = {} 
    finish_reason = None

    for event in stream:
        event_data = event.model_dump()
        print(event_data )
        choices = event_data.get("choices", [{}])
        
        unknown_chunk = True

        if choices:
            message_chunk = choices[0].get("delta", {})
            print("message_chunk", message_chunk)

            if chunk := message_chunk.get("reasoning", None):
                unknown_chunk = False
                print("Reasoning:", chunk)
                collected_reasoning.append(chunk)

            if chunk := message_chunk.get("thinking", None):
                unknown_chunk = False
                print("Thinking:", chunk)
                collected_reasoning.append(chunk)

            if chunk := message_chunk.get("content", None):
                unknown_chunk = False
                print("Content", chunk)
                collected_content.append(chunk)

            if tool_calls := message_chunk.get("tool_calls", None):
                unknown_chunk = False
                for tool_call in tool_calls:
                    index = tool_call.get("index", 0)
                    # Initialize buffer slot if this is a new tool call item
                    if index not in tool_calls_buffer:
                        tool_calls_buffer[index] = { "name": "", "arguments_stream": "", "id": "", "index":0}
                    if tool_call_id := tool_call.get("id"):
                        tool_calls_buffer[index]["id"] +=  tool_call_id
                    if func := tool_call.get("function"):
                        if fname := func.get("name"):
                            tool_calls_buffer[index]["name"] += fname
                        if arguments := func.get("arguments"):
                            tool_calls_buffer[index]["arguments_stream"] += arguments
                    print("ToolCall", tool_calls_buffer[index])

            if new_finish_reason := choices[0].get("finish_reason"):
                unknown_chunk = False
                finish_reason = new_finish_reason
                print("finish_reason", finish_reason)

        if usage := event_data.get("usage", None):
            unknown_chunk = False
            print("Usage:", usage)
             
        if unknown_chunk:
            print("Unknown Chunk: ", event_data)

    final_tool_calls = []
    for index, partial_call in tool_calls_buffer.items():
        # Parse the gathered argument string pieces into a final Python dictionary
        try:
            parsed_args = json.loads(partial_call["arguments_stream"])
        except json.JSONDecodeError:
            # Fallback if the string fragment format requires sanitization
            parsed_args = partial_call["arguments_stream"]
        final_tool_calls.append({"id": partial_call["id"], "name": partial_call["name"], "arguments": parsed_args })

    completion_tokens = api_response.get("usage", {}).get("completion_tokens", 0),
    prompt_tokens = api_response.get("usage", {}).get("prompt_tokens", 0),

    return {
        "reasoning": "".join(collected_reasoning),
        "content": "".join(collected_content),
        "tool_calls": final_tool_calls
    }


if __name__ == "__main__":
    print(run_streaming_session())
