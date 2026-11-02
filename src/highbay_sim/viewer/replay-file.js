// Loads and checks replay data. A file that fails a check is never used, even in part.

export const SUPPORTED_FORMAT_VERSION = 1;

const ARRAY_PARTS = ["articles", "initial_stock", "orders", "events"];
const OBJECT_PARTS = ["run", "warehouse", "reported"];

function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function problemIn(content) {
  if (!isObject(content)) {
    return "The replay file does not contain a replay.";
  }
  if (content.format_version !== SUPPORTED_FORMAT_VERSION) {
    return (
      `The replay file has format version ${content.format_version}, ` +
      `but this viewer supports version ${SUPPORTED_FORMAT_VERSION}.`
    );
  }
  for (const part of ARRAY_PARTS) {
    if (!Array.isArray(content[part])) {
      return `The replay file is damaged: "${part}" is missing or has the wrong structure.`;
    }
  }
  for (const part of OBJECT_PARTS) {
    if (!isObject(content[part])) {
      return `The replay file is damaged: "${part}" is missing or has the wrong structure.`;
    }
  }
  return null;
}

/** Returns {data, error}, where exactly one of the two is null. */
export function parseReplay(text) {
  let content;
  try {
    content = JSON.parse(text);
  } catch (error) {
    return { data: null, error: `The replay file is damaged and cannot be read: ${error.message}` };
  }
  const problem = problemIn(content);
  return problem ? { data: null, error: problem } : { data: content, error: null };
}

export async function loadReplay(url) {
  let response;
  try {
    response = await fetch(url);
  } catch (error) {
    return { data: null, error: `The replay file could not be loaded: ${error.message}` };
  }
  if (!response.ok) {
    return { data: null, error: `The replay file could not be loaded (${response.status}).` };
  }
  return parseReplay(await response.text());
}
