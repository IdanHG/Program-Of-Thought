from typing import Dict, Any

from openai import OpenAI
import re

#SetUp

client = OpenAI(
    organization='$<ORGANIZATION_ID>',
    project='$<PROJECT_ID>',
    api_key='$<API_KEY>',
)

def createPrompt(problem: str) -> str:
    """Create a Program of Though prompt for the given problem."""
    return f"""Solve the following problem by writing a Python code. Your reasoning should be as follows:
    First think about the best approach, Second implement the solution with a pyhton code, and finally run it and provide the answer.
    
    Problem: {problem}
    
    Your response should include:
    1. Your reasoning process explained step-by-step in detail.
    2. Python code that solves the problem. The code part should follow this regular expression:```python\s*(.*?)\s*``` to allow easy parsing
    3. An estimation of the result
    
    Make sure your code is correct, efficient as possible and handles all edge cases.  
    """

def get_code(response: str) -> str:
    """Extract the code from model's response"""

    #find python code block
    code_finder = r"```python\s*(.*?)\s*```"
    match = re.search(code_finder, response, re.DOTALL)
    if match:
        return match.group(1) #only what's inside the parenthesis

    #look for other forms of code blocks (such as inside the text itself)
    else:
        lines = response.split("\n")
        code_lines = []
        in_code = False

        for line in lines:
            if line.strip().startswith("def ") or line.strip().startswith("if __name__ ==") or line.strip().startswith("import "):
                in_code = True

            if in_code:
                code_lines.append(line)

            if in_code and len(code_lines) > 0 and line.strip() == '':
                in_code = False

    return '\n'.join(code_lines)

def execute(code: str) -> Dict[str, Any]:
    """Execute the code and return results"""
    local_vars = {}
    try:
        exec(code, {"__builtins__": __builtins__}, local_vars)
        return {"success":  True, "result": local_vars, "error": None}
    except Exception as e:
        return {"success": False, "result" : None, "error": str(e)}

def create_result_prompt(problem: str, original_response:str, formatted_results: str) -> str:
    """Create the result prompt"""
    return f"""Your previous response analysis to the problem was:
    
    Problem: {problem}
    
    Your original response and code were:
    {original_response}
    
    the code was executed successfully. Here are all the variables and their values:
    {formatted_results}
    
    Based on these execution results, please:
    1. Interpret what the results mean in the context of the original problem
    2. Explain if the results confirm your initial reasoning or if adjustments are needed
    3. Provide a final, clear answer to the original problem
    4. If there were any errors or unexpected results, explain what went wrong and how it could be fixe
    """

def format_execution(execution_results: Dict[str, Any]) -> str:
    """Format the execution results to make the results easier to understand"""

    if not execution_results["success"]:
        return f"Error while executing code: {execution_results['error']}"

    if execution_results["result"] is None:
        return "No variables were computed"

    formatted_execution_results = ""

    for var, value in execution_results["result"].items():
        if var.startswith("__"):
            continue
        value = repr(value)
        formatted_execution_results += f"{var} = {value}\n"

    return formatted_execution_results


def program_of_thought(problem: str, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """Solve problem using Program of Thought prompting"""
    prompt = createPrompt(problem)

    #get prompt response from wanted model
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "system", "content": "You are a skillful Python developer who solves problems step by step"},
        ],
        max_tokens = 3000,
        #set randomness and creativity to low to get predictable and reliable code
        temperature = 0.2
    )

    #parse response
    response_content = response.choices[0].message.content
    response_code = get_code(response_content)

    #get_code found no code
    if not response_code:
        return {
            "success": False,
            "original response": response_content,
            "error": "No code found in response",
            "code": None,
            "execution_results": None,
            "final response": None,
            "final answer": None
        }

    #execute and prepare result for final prompt
    execution_results = execute(response_code)
    formatted_execution_results = format_execution(execution_results)
    #result prompt with execution results
    final_prompt = create_result_prompt(problem, response_content, formatted_execution_results)


    final_response = client.chat.completions.create(
        model=model,
        messages=[
            #give context and entire process before generating final answer
            {"role": "user", "content": prompt},
            {"role": "system", "content": "You are a skillful Python developer who solves problems step by step"},
            {"role": "assistant", "content": response_content},
            {"role": "user", "content": final_prompt}
        ],
        max_tokens = 3000,
        temperature = 0.2
    )
    final_response_content = final_response.choices[0].message.content

    return {
        "success": execution_results["success"],
        "original response": response_content,
        "error": None,
        "code": response_code,
        "execution_results": execution_results,
        "final response": final_response,
        "final answer": final_response_content
    }

def POT_to_string(result: Dict[str, Any]) -> str:
    """Format Program of Thought results into a well-structured, readable string."""

    # Handle error case
    if not result["success"]:
        output = "❌ ERROR: " + str(result.get("error", "Unknown error")) + "\n\n"
        if result.get("original response"):
            output += "ORIGINAL RESPONSE:\n" + result["original response"]
        return output

    # Success case - build structured output
    output = "📝 PROGRAM OF THOUGHT RESULTS\n"
    output += "=" * 50 + "\n\n"

    # Original analysis section
    output += "🔍 ORIGINAL ANALYSIS:\n"
    output += "-" * 50 + "\n"
    output += result["original response"] + "\n\n"

    # Code section
    output += "💻 EXTRACTED CODE:\n"
    output += "-" * 50 + "\n"
    output += result["code"] + "\n\n"

    # Execution results section
    output += "🧪 EXECUTION RESULTS:\n"
    output += "-" * 50 + "\n"
    output += format_execution(result["execution_results"]) + "\n\n"

    # Final response section
    output += "✅ FINAL ANSWER:\n"
    output += "-" * 50 + "\n"
    output += result["final answer"] + "\n"

    output += "=" * 50

    return output

# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    problem = input("Enter a problem that can be solved via calculation / code: \n")
    result = program_of_thought(problem)
    print(POT_to_string(result))