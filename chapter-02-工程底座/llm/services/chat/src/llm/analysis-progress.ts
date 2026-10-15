export interface AnalysisProgress {
  step: string;
  label: string;
  status: 'running' | 'completed' | 'failed';
}

export interface AnalysisRunOptions {
  signal?: AbortSignal;
  onProgress?: (event: AnalysisProgress) => void;
}

export async function trackAnalysis<T>(
  options: AnalysisRunOptions,
  step: string,
  label: string,
  run: () => Promise<T>,
): Promise<T> {
  options.signal?.throwIfAborted();
  options.onProgress?.({ step, label, status: 'running' });
  try {
    const result = await run();
    options.signal?.throwIfAborted();
    options.onProgress?.({ step, label, status: 'completed' });
    return result;
  } catch (error) {
    options.onProgress?.({ step, label, status: 'failed' });
    throw error;
  }
}
