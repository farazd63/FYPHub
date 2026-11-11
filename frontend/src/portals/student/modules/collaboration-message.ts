export const COLLABORATION_MESSAGE_LIMIT = 4000;

export function validateCollaborationMessage(text: string): string | null {
  if (!text.trim()) return "Enter a message before sending.";
  if (text.length > COLLABORATION_MESSAGE_LIMIT) return `Messages must be ${COLLABORATION_MESSAGE_LIMIT} characters or fewer.`;
  return null;
}

export function sendsOnEnter(event: { key: string; shiftKey: boolean; isComposing: boolean }): boolean {
  return event.key === "Enter" && !event.shiftKey && !event.isComposing;
}

export function mergeCollaborationMessages<T extends { id: number }>(previous: T[], incoming: T[]): T[] {
  const unique = new Map(previous.map(message => [message.id, message]));
  incoming.forEach(message => unique.set(message.id, message));
  return [...unique.values()].sort((left, right) => left.id - right.id);
}
