from dataclasses import dataclass
from pathlib import Path
import logging

import weave
import simple_parsing
from vllm import LLM, SamplingParams
from mini_lib.problem import Problem
from mini_lib.utils import maybe_remove_backticks, check_solution, setup_logger, run,TimeoutException
import re
from transformers import AutoTokenizer, AutoModelForCausalLM, GenerationConfig
import torch


import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
model_name = "deepseek-ai/deepseek-coder-7b-instruct-v1.5"
# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name)

@weave.op
def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

llm = LLM(model=model_name, dtype="float16")

@weave.op
def call_model(messages, **kwargs):
    # Preprocess messages to ensure they are in the correct format
    processed_messages = []
    for message in messages:
        if isinstance(message, dict):
            content = message['content']
            role = message['role']
        elif isinstance(message, str):
            # Assume it's a user message if it's a string
            content = message
            role = "user"
        else:
            raise ValueError(f"Unexpected message format: {type(message)}")

        if isinstance(content, list):
            # Join text items and ignore image items
            text_content = ' '.join(item['text'] for item in content if item.get('type') == 'text')
            processed_messages.append({"role": role, "content": text_content})
        else:
            processed_messages.append({"role": role, "content": content})

    # Format messages for VLLM
    prompt = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in processed_messages])
    prompt += "\nAssistant:"

    # Set up sampling parameters
    sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=4000)

    # Generate
    outputs = llm.generate([prompt], sampling_params)
    print(prompt)
    prompt_tokens = count_tokens(prompt)
    print(f"Prompt Tokens: {prompt_tokens}")
    outputs_tokens = count_tokens(outputs[0].outputs[0].text.strip())
    print(f"outputs Tokens: {outputs_tokens}")
    # Return the generated text
    return outputs[0].outputs[0].text.strip()

@weave.op
async def generate_code(
    problem: Problem, 
    system_prompt: str, 
    prompt_template: str, 
    extract_prompt: str,
    use_images: bool = False) -> str:
    logging.info(f"Generating code solution for: {problem.name}")

    # Count tokens for problem components
    problem_description_tokens = count_tokens(problem.problem_description)
    sample_input_tokens = count_tokens(problem.sample_input)
    sample_output_tokens = count_tokens(problem.sample_output)
    total_problem_tokens = problem_description_tokens + sample_input_tokens + sample_output_tokens

    # Count tokens for prompts
    system_prompt_tokens = count_tokens(system_prompt)
    
    # Format the prompt template with problem details
    formatted_prompt = prompt_template.format(
        problem_description=problem.problem_description,
        sample_input=problem.sample_input,
        sample_output=problem.sample_output,
    )
    prompt_template_tokens = count_tokens(formatted_prompt)
    
    extract_prompt_tokens = count_tokens(extract_prompt)

    # Print token counts
    print(f"Token counts:")
    print(f"  Problem description: {problem_description_tokens}")
    print(f"  Sample input: {sample_input_tokens}")
    print(f"  Sample output: {sample_output_tokens}")
    print(f"  Total problem: {total_problem_tokens}")
    print(f"  System prompt: {system_prompt_tokens}")
    print(f"  Prompt template: {prompt_template_tokens}")
    print(f"  Extract prompt: {extract_prompt_tokens}")
    print(f"  Total prompts: {system_prompt_tokens + prompt_template_tokens + extract_prompt_tokens}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": prompt_template.format(
                problem_description=problem.problem_description,
                sample_input=problem.sample_input,
                sample_output=problem.sample_output,
            )}
        ] + ([{"type": "image_url", "image_url": {"url": img}} for img in problem.images] if use_images else [])}
    ]

    # call model one first time to get the code
    out = call_model(messages=messages)

    logging.info("Generating initial analysis and solution")


    # Let's make a second call to the model to extract the code from the response
    messages.append({"role": "assistant", "content": out})
    messages.append({"role": "user", "content": [
        {"type": "text", 
         "text": extract_prompt}
    ]})

    # call model second time to extract the code
    solution = call_model(messages=messages)
    logging.info("Extracting the solution from the previous generation...")

    code_match = re.search(r'```python\n(.*?)```', solution, re.DOTALL)
    if code_match:
        extracted_code = code_match.group(1).strip()
    else:
        extracted_code = ""
        logging.error("No Python code found in the solution")


    # in case we have ```python stuff...`
    # solution = maybe_remove_backticks(solution)
    return extracted_code

# system_prompt="""
# You are a world-class competitive programmer tasked with solving a programming problem. 
# You will be provided with a problem statement, and you need to create a Python3 solution for it. 
# Your task it to develop a winning solution to the problem in Python3 programming language.
# You will do this in a step-by-step manner.

# Step 1: Extract the core question and the problem-solving information from the problem statement.
# Step 2: Describe the algorithm used to solve the problem.
# Step 3: Write a short tutorial on the algorithm and how it works.
# Step 4: Generate a step by step plan to solve the problem.
# Step 5: Generate the pseudocode to solve the problem.
# Step 6: Write the final solution in Python3 programming language to solve the problem.

# Competition Guidelines:
#     a. Use the function signature: 'def solve(input_data: str) -> str:'
#     b. Handle input and output using standard input/output (stdin/stdout)
#     c. Optimize for execution time where possible, without compromising correctness.
#     c. Use 'from tqdm import tqdm' for progress bars in loops processing large datasets.
#     d. Do not add extra print statements otherwise it will fail the test cases.
#     e. Make sure your code passes all potential test cases, including edge cases
#     f. Follow the input/output format specified in the problem statement and the sample test cases.

# """
# system_prompt = """
# You are an expert problem solver with a focus on creating accurate and efficient Python code. Your primary task is to develop a solution that precisely addresses the given problem. Your code should prioritize correctness and adherence to the problem specifications, while also optimizing for execution time where possible. Always handle input and output as strings, and ensure your solution covers all aspects of the problem description.

# Key Requirements:
# 1. Use the function signature: 'def solve(input_data: str) -> str:'
# 2. Implement an algorithm that correctly solves all aspects of the problem.
# 3. Ensure your solution handles all cases mentioned in the problem description.
# 4. ptimize for execution time where possible, without compromising correctness.
# 5. Use 'from tqdm import tqdm' for progress bars in loops processing large datasets.
# 6. Include any necessary imports at the beginning of your code.

# Important Notes:
# - Carefully read and address all parts of the problem description.
# - Your solution must handle edge cases and any specific conditions mentioned in the problem.
# - Prioritize correctness over optimization; ensure your code works correctly for all possible inputs.
# """

system_prompt="""
You are an expert Python developer specializing in algorithmic problem-solving. Your task is to create highly efficient and accurate Python code that precisely addresses the given problem. Your solution should prioritize correctness, optimal performance, and adherence to all problem specifications.

Key Requirements:
1. Use the function signature: 'def solve(input_data: str) -> str:'
2. Implement an algorithm that correctly solves all aspects of the problem, including edge cases.
3. Optimize for both time and space complexity where possible, without compromising correctness.
4. Use 'from tqdm import tqdm' for progress bars in loops processing large datasets.
5. Include all necessary imports at the beginning of your code.
6. Handle input and output as strings, parsing and formatting as required.
7. Provide clear, concise comments explaining complex logic or optimizations.

Best Practices:
- Carefully analyze the problem description to identify all requirements and constraints.
- Consider various algorithmic approaches and choose the most efficient one for the given problem.
- Implement robust error handling and input validation where appropriate.
- Use appropriate data structures to optimize time and space complexity.
- Write clean, readable code following PEP 8 style guidelines.
- If applicable, consider using Python's built-in functions and libraries for optimization.

Remember: Your primary goal is to create a solution that is both correct and efficient, capable of handling all possible inputs within the problem's constraints.
"""
prompt_template = """
Problem Description:
{problem_description}

Sample Input:
{sample_input}

Sample Output:
{sample_output}

Your task is to create a Python function named 'solve' that accurately and efficiently solves the problem described above. The function should take a string input similar to the sample input and return a string output similar to the sample output.

Requirements:
1. Implement the 'solve' function with the signature: def solve(input_data: str) -> str:
2. Parse the input string correctly and handle all aspects of the problem.
3. Optimize the algorithm for both time and space complexity.
4. Use 'tqdm' for progress bars in loops processing large datasets, if applicable.
5. Include necessary imports at the beginning of your code.
6. Provide brief comments explaining any complex logic or optimizations.

The file should have a single `solve` method with the following signature:

```python
from tqdm import tqdm

def solve(input_data: str) -> str:
    # Your implementation here
"""

extract_prompt = """
Extract the code from the response. reply with the code only. Omit any additional example or explanation.
- If the solution involves a for loop, please use `for sample in tqdm(range(samples))` to show progress.
- The code should be a valid python program.
- Get the `solve` function with the corresponding imports"""

@weave.op
def solve_problem(problem: Problem, use_images=False, timeout=60) -> dict:
    code = generate_code(
        problem, 
        system_prompt=system_prompt, 
        prompt_template=prompt_template, 
        extract_prompt=extract_prompt, 
        use_images=use_images)
    print(code)

    input_data, output = problem.sample_input, problem.sample_output
    generated_output = run(code, input=input_data, timeout=timeout) 
    
    return {"code": code, "generated_output": generated_output, "expected_output": output}

@dataclass
class Args(simple_parsing.Serializable):
    problem_name: str = "cheeseburger_corollary_ch1" # name of the problem to solve
    folder_path: Path = Path("./dataset/2023/practice/") # path to the folder containing the problems
    weave_log: bool = True # set to True to log to weave
    use_images: bool = False # set to True to use images in the prompt
    save_output: bool = True # set to True to save the output to a file
    debug: bool = False # set to True to see the debug logs
    timeout: int = 60 # timeout for the code execution

if __name__=="__main__":
    args = simple_parsing.parse(Args)

    setup_logger(args.debug)

    problem = Problem.from_name(args.problem_name, args.folder_path)

    if args.weave_log: 
        weave.init("hack-starter")
    
    logging.info("> Solving on sample input...")
    try:
        problem_solution = solve_problem(problem, use_images=args.use_images, timeout=args.timeout)
    except TimeoutException:
        print("The solution took too long to execute and was terminated.")
        problem_solution = None  # or some default value
    matches = check_solution(problem_solution["expected_output"], problem_solution["generated_output"])
    logging.info("Sample Matches:")
    logging.info(matches)

    logging.info("> Solving on full input...")
    expected_output = problem.get_output()
    generated_output = run(problem_solution["code"], input=problem.get_input(), timeout=args.timeout) 
    matches = check_solution(expected_output, generated_output)
    logging.info("Final Matches:")
    logging.info(matches)

    if args.save_output:
        logging.info("> Saving output to files")
        problem.save_output(problem_solution["generated_output"])
        problem.save_code(problem_solution["code"])

