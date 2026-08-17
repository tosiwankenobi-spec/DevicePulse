import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Canvas, Path, Skia, SweepGradient, vec, Group, BlurMask } from '@shopify/react-native-skia';
import { useSharedValue, withTiming, Easing } from 'react-native-reanimated';
import { theme } from '../theme';

interface Props {
  score: number;
  size?: number;
  label?: string;
  testID?: string;
}

export const HealthRing: React.FC<Props> = ({ score, size = 240, label = 'Health Score', testID }) => {
  const progress = useSharedValue(0);

  useEffect(() => {
    progress.value = withTiming(Math.max(0, Math.min(100, score)) / 100, {
      duration: 1400,
      easing: Easing.out(Easing.cubic),
    });
  }, [score]);

  const stroke = size * 0.09;
  const radius = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;

  const bgPath = Skia.Path.Make();
  bgPath.addCircle(cx, cy, radius);

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }} testID={testID}>
      <Canvas style={{ position: 'absolute', width: size, height: size }}>
        <Path path={bgPath} style="stroke" strokeWidth={stroke} color={theme.color.border} strokeCap="round" />
        <Group origin={vec(cx, cy)} transform={[{ rotate: -Math.PI / 2 }]}>
          <Path
            path={bgPath}
            style="stroke"
            strokeWidth={stroke}
            strokeCap="round"
            start={0}
            end={score / 100}
          >
            <SweepGradient c={vec(cx, cy)} colors={['#0EA5E9', '#10B981', '#10B981']} />
            <BlurMask blur={4} style="solid" />
          </Path>
        </Group>
      </Canvas>
      <View style={styles.center} pointerEvents="none">
        <Text style={styles.score} testID="health-score-value">{Math.round(score)}</Text>
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
