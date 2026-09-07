# Decision: chose DeepSeek for the personal-AI project

Date: 2024-11-03

Re-sending the full personal history every turn is too expensive on OpenAI
($2.50/M input) and Claude. DeepSeek's prefix-cache discounts repeated prefix
tokens to $0.07/M. For a 20k-token personal history that is the difference
between dollars and cents per turn.

Going with DeepSeek-V3 (deepseek-chat) for v0.1. Revisit if a US-priced model
ships a comparable prefix-cache discount.
