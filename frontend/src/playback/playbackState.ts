export function nextPlaybackIndex(
  currentIndex: number,
  frameCount: number,
  candidateIndices: number[],
): number {
  if (candidateIndices.length > 0) {
    const nextCandidate = candidateIndices.find((frameIndex) => frameIndex > currentIndex);
    return nextCandidate ?? candidateIndices[candidateIndices.length - 1];
  }
  return Math.min(Math.max(0, frameCount - 1), currentIndex + 1);
}

export function previousPlaybackIndex(
  currentIndex: number,
  candidateIndices: number[],
): number {
  if (candidateIndices.length > 0) {
    const previousCandidates = candidateIndices.filter((frameIndex) => frameIndex < currentIndex);
    return previousCandidates.at(-1) ?? candidateIndices[0];
  }
  return Math.max(0, currentIndex - 1);
}
