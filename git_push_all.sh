#!/bin/bash

current_branch=$(git branch --show-current)

if [ -z "$current_branch" ]; then
  echo "Errore: Non è stato possibile determinare il branch corrente."
  exit 1
fi

echo "Eseguo il push del branch '$current_branch' su 'origin' e 'github'..."

git push -u origin "$current_branch"
git push -u github "$current_branch"

echo "Push completato."
