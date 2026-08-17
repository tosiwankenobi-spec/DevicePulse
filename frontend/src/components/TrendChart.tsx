import React from 'react';
import { View, Platform } from 'react-native';

export interface TrendPoint { label: string; score: number; cleaned: boolean }

interface Props { points: TrendPoint[]; width: number; height?: number }

const MIN = 40;
const MAX = 100;

function coords(points: TrendPoint[], width: number, height: number, padX: number, padY: number) {
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  return points.map((p, i) => {
    const x = padX + (innerW * i) / Math.max(1, points.length - 1);
    const t = (p.score - MIN) / (MAX - MIN);
    const y = padY + innerH * (1 - Math.max(0, Math.min(1, t)));
    return { x, y, p };
  });
}

export const TrendChart: React.FC<Props> = ({ points, width, height = 180 }) => {
  if (Platform.OS === 'web') {
    return <WebChart points={points} width={width} height={height} />;
  }
  const Native = require('./TrendChart.native').TrendChart;
  return <Native points={points} width={width} height={height} />;
};

const WebChart: React.FC<Props> = ({ points, width, height = 180 }) => {
  const padX = 16;
  const padY = 20;
  const pts = coords(points, width, height, padX, padY);

  const segments = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i];
    const b = pts[i + 1];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
    segments.push(
      <View
        key={`seg-${i}`}
        style={{
          position: 'absolute',
          left: a.x,
          top: a.y,
          width: len,
          height: 3,
          backgroundColor: '#10B981',
          borderRadius: 2,
          transform: [{ translateY: -1.5 }, { rotate: `${angle}deg` }],
          transformOrigin: 'left center' as any,
        }}
      />
    );
  }

  return (
    <View style={{ width, height }}>
      {segments}
      {pts.map((c, i) => (
        <View
          key={`dot-${i}`}
          style={{
            position: 'absolute',
            left: c.x - 5,
            top: c.y - 5,
            width: 10,
            height: 10,
            borderRadius: 5,
            backgroundColor: c.p.cleaned ? '#10B981' : '#0B1B24',
            borderWidth: 2,
            borderColor: '#10B981',
          }}
        />
      ))}
    </View>
  );
};
