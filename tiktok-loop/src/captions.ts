// Adjust startMs / endMs to match your actual voiceover.mp3 timing.
// Current values are estimates based on a natural 38-second read.
export type Caption = { text: string; startMs: number; endMs: number };

export const captions: Caption[] = [
  { text: 'Ever notice how you always lose control', startMs: 300, endMs: 2800 },
  { text: 'at the same time of day?', startMs: 2800, endMs: 5000 },
  { text: 'Not randomly.', startMs: 7400, endMs: 9000 },
  { text: 'The same window.', startMs: 9000, endMs: 10400 },
  { text: 'Every time.', startMs: 10400, endMs: 11800 },
  { text: "There's a reason for that.", startMs: 12400, endMs: 14900 },
  { text: 'Your dopamine peaks in the morning...', startMs: 15300, endMs: 18000 },
  { text: '...and crashes at night.', startMs: 18000, endMs: 20400 },
  { text: 'When dopamine drops,', startMs: 22200, endMs: 23700 },
  { text: 'your brain scans for the fastest option.', startMs: 23700, endMs: 26800 },
  { text: 'That scan lasts four minutes.', startMs: 27300, endMs: 29600 },
  { text: 'Whatever habit is most wired in...', startMs: 29600, endMs: 31300 },
  { text: 'wins.', startMs: 31300, endMs: 32100 },
  { text: "This isn't a willpower problem.", startMs: 31600, endMs: 33300 },
  { text: "It's a timing problem.", startMs: 33300, endMs: 35000 },
  { text: 'The loop always runs in the same window—', startMs: 34900, endMs: 36700 },
  { text: 'which means it can be mapped.', startMs: 36700, endMs: 38000 },
];
