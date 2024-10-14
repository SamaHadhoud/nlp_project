from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

# class VLLMSingleton:
#     _instance = None

#     @classmethod
#     def get_instance(cls):
#         if cls._instance is None:
#             print("Initializing vLLM model for the first time...")
#             cls._instance = cls()
#         return cls._instance

#     def __init__(self):
#         model_name = "deepseek-ai/deepseek-coder-7b-instruct-v1.5"
#         self.llm = LLM(model=model_name, 
#                        trust_remote_code=True, 
#                        dtype="float16", 
#                        gpu_memory_utilization=0.95)
        
#         self.default_sampling_params = SamplingParams(temperature=0.1, top_p=0.95, max_tokens=1024)
        
#         # Initialize the tokenizer
#         self.tokenizer = AutoTokenizer.from_pretrained(model_name)

#     def generate(self, prompt, sampling_params=None):
#         if sampling_params is None:
#             sampling_params = self.default_sampling_params
#         outputs = self.llm.generate([prompt], sampling_params)
#         return outputs[0].outputs[0].text

#     def tokenize(self, text):
#         return self.tokenizer.encode(text)

#     def detokenize(self, token_ids):
#         return self.tokenizer.decode(token_ids)

# def get_vllm():
#     return VLLMSingleton.get_instance()

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

class VLLMSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            print("Initializing vLLM model for the first time...")
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        model_name = "Qwen/Qwen2.5-Coder-7B-Instruct"
        self.llm = LLM(model=model_name, 
                       trust_remote_code=True, 
                       dtype="float16", 
                       gpu_memory_utilization=0.98,
                       max_model_len=8000)
        
        self.default_sampling_params = SamplingParams(temperature=0.1, top_p=0.95, max_tokens=8000)
        
        # Initialize the tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def generate(self, prompts, sampling_params=None):
        if sampling_params is None:
            sampling_params = self.default_sampling_params
        outputs = self.llm.generate(prompts, sampling_params)
        return outputs

    def tokenize(self, text):
        return self.tokenizer.encode(text)

    def detokenize(self, token_ids):
        return self.tokenizer.decode(token_ids)

def get_vllm():
    return VLLMSingleton.get_instance()