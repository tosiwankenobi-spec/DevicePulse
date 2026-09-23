import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { theme } from '../theme';

interface Props {
  score: number;
  size?: number;
  label?: string;
  testID?: string;
}

// Cross-platform ring: uses Skia natively, DOM SVG on web.
export const HealthRing: React.FC<Props> = ({ score, size = 240, label = 'Health Score', testID }) => {
  if (Platform.OS === 'web') {
    return <WebRing score={score} size={size} label={label} testID={testID} />;
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Native = require('./HealthRing.native').HealthRing;
  return <Native score={score} size={size} label={label} testID={testID} />;
};

const WebRing: React.FC<Props> = ({ score, size = 240, label = 'Health Score', testID }) => {
  const stroke = size * 0.09;
  const safeScore = Math.max(0, Math.min(100, score));

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }} testID={testID}>
      {/* Base track */}
      <View style={{ position: 'absolute', width: size, height: size, borderRadius: size / 2, borderWidth: stroke, borderColor: theme.color.border }} />
      {/* Progress arc via SVG (works on web via react-native-svg -> not available. Use inline CSS trick with box-shadow gradient.) */}
      {/* Simpler: render a "conic" via multiple slices using inline HTML div in web only. */}
      {/* @ts-ignore - web only div */}
      <div
        style={{
          position: 'absolute',
          width: size,
          height: size,
          borderRadius: '50%',
          background: `conic-gradient(#10B981 0deg, #0EA5E9 ${(safeScore / 100) * 360}deg, rgba(22,51,66,0.9) ${(safeScore / 100) * 360}deg 360deg)`,
          WebkitMask: `radial-gradient(circle, transparent ${(size - stroke * 2) / 2}px, black ${(size - stroke * 2) / 2 + 1}px)`,
          mask: `radial-gradient(circle, transparent ${(size - stroke * 2) / 2}px, black ${(size - stroke * 2) / 2 + 1}px)`,
        }}
      />
      <View style={styles.center} pointerEvents="none">
        <Text style={styles.score} testID="health-score-value">{Math.round(safeScore)}</Text>
        <Text style={styles.label}>{label}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center' },
  score: { color: theme.color.onSurface, fontSize: 56, fontWeight: '800', letterSpacing: -1 },
  label: { color: theme.color.onSurface2, fontSize: 13, marginTop: 4, letterSpacing: 0.5, textTransform: 'uppercase' },
});
