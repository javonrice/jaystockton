import { loadFont as loadSyne } from '@remotion/google-fonts/Syne';
import { loadFont as loadDMSans } from '@remotion/google-fonts/DMSans';

export const { fontFamily: SYNE } = loadSyne('normal', {
  weights: ['700'],
  subsets: ['latin'],
});

export const { fontFamily: DM_SANS } = loadDMSans('normal', {
  weights: ['400', '500'],
  subsets: ['latin'],
});
