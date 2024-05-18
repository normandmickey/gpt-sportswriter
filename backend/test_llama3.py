import requests

API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B"
headers = {"Authorization": "Bearer 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"}

def query(payload):
	response = requests.post(API_URL, headers=headers, json=payload)
	return response.json()
	
output = query({
	"inputs": "How many feet in a mile",
})

print(output)