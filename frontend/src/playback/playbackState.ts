export function nextPlaybackIndex(
  current: number,
  frameCount: number,
  failureFrameIndices: number[],
): number {
  if (failureFrameIndices.length > 0) {
    return failureFrameIndices.find((frameIndex) => frameIndex > current) ?? failureFrameIndices.at(-1)!;
  }
  return Math.min(frameCount - 1, current + 1);
}

export function previousPlaybackIndex(current: number, failureFrameIndices: number[]): number {
  if (failureFrameIndices.length > 0) {
    const previous = failureFrameIndices.filter((frameIndex) => frameIndex < current);
    return previous.at(-1) ?? failureFrameIndices[0];
  }
  return Math.max(0, current - 1);
}
