import React from 'react';
import { View } from 'react-native';
import { Canvas, Path, Skia, LinearGradient, vec, Circle } from '@shopify/react-native-skia';

export interface TrendPoint { label: string; score: number; cleaned: boolean }
interface Props { points: TrendPoint[]; width: number; height?: number }

const MIN = 40;
const MAX = 100;

export const TrendChart: React.FC<Props> = ({ points, width, height = 180 }) => {
  const padX = 16;
  const padY = 20;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  const pts = points.map((p, i) => {
    const x = padX + (innerW * i) / Math.max(1, points.length - 1);
    const t = (p.score - MIN) / (MAX - MIN);
    const y = padY + innerH * (1 - Math.max(0, Math.min(1, t)));
    return { x, y, cleaned: p.cleaned };
  });

  const line = Skia.Path.Make();
  const area = Skia.Path.Make();
  pts.forEach((c, i) => {
    if (i === 0) { line.moveTo(c.x, c.y); area.moveTo(c.x, height - padY); area.lineTo(c.x, c.y); }
    else { line.lineTo(c.x, c.y); area.lineTo(c.x, c.y); }
  });
  if (pts.length) area.lineTo(pts[pts.length - 1].x, height - padY);
  area.close();

  return (
    <View style={{ width, height }}>
      <Canvas style={{ flex: 1 }}>
        <Path path={area} style="fill" opacity={0.18}>
          <LinearGradient start={vec(0, 0)} end={vec(0, height)} colors={['#10B981', 'transparent']} />
        </Path>
        <Path path={line} style="stroke" strokeWidth={3} strokeCap="round" strokeJoin="round">
          <LinearGradient start={vec(0, 0)} end={vec(width, 0)} colors={['#0EA5E9', '#10B981']} />
        </Path>
        {pts.map((c, i) => (
          <Circle key={i} cx={c.x} cy={c.y} r={5} color={c.cleaned ? '#10B981' : '#0B1B24'} />
        ))}
        {pts.map((c, i) => (
          <Circle key={`ring-${i}`} cx={c.x} cy={c.y} r={5} style="stroke" strokeWidth={2} color="#10B981" />
        ))}
      </Canvas>
    </View>
  );
};
