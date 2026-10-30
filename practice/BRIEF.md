# Synthetic practice: stock check

This is an invented practice task. It is not a contest task or prediction.

Create a small local service that reads a CSV with `item_id`, `stock`, and `minimum` columns. Report rows where stock is strictly less than minimum. Preserve the original item ID and show the total number of low-stock items. Reject missing columns, empty numeric values, non-finite numbers, negative quantities, duplicate IDs, and an empty data file with a clear error. Do not silently turn missing values into zero.

Use the provided sample and boundary files. Decide and document whether data survives a refresh or restart. Keep setup simple and use the local environment. No external model API, remote deployment, or credential is required. Have a person verify the UI manually if you create one.

Deliver the code, a run guide, and a brief verification note. Use your own filenames and map them to task.json. Add assertions based on hand-calculated expectations. This folder intentionally does not include the completed service.

After finishing the practice, turn off AI assistance and answer these questions in your own words, five minutes each:

1. What does the service do and how did you check it?
2. What did you delegate to AI and what did you decide yourself?
3. Which alternative did you consider and why did you choose your approach?
4. What actual failure occurred and how did you verify the fix? If none occurred, say so.
5. What remains unverified or limited?
6. How did you allocate time between implementation, verification, and handoff?
