import React from 'react';
import { View } from 'react-native';
import { Canvas, Path, Skia, LinearGradient, vec, Circle, Group } from '@shopify/react-native-skia';

interface Props {
  size?: number;
  glow?: boolean;
}

export const VLogo: React.FC<Props> = ({ size = 120, glow = true }) => {
  const s = size;

  const vPath = Skia.Path.Make();
  vPath.moveTo(s * 0.15, s * 0.18);
  vPath.lineTo(s * 0.30, s * 0.18);
  vPath.lineTo(s * 0.50, s * 0.72);
  vPath.lineTo(s * 0.70, s * 0.18);
  vPath.lineTo(s * 0.85, s * 0.18);
  vPath.lineTo(s * 0.56, s * 0.90);
  vPath.lineTo(s * 0.44, s * 0.90);
  vPath.close();

  const circuit = Skia.Path.Make();
  circuit.moveTo(s * 0.32, s * 0.30);
  circuit.lineTo(s * 0.42, s * 0.30);
  circuit.lineTo(s * 0.46, s * 0.38);
  circuit.moveTo(s * 0.68, s * 0.30);
  circuit.lineTo(s * 0.58, s * 0.30);
  circuit.lineTo(s * 0.54, s * 0.38);
  circuit.moveTo(s * 0.50, s * 0.50);
  circuit.lineTo(s * 0.50, s * 0.62);

  return (
    <View style={{ width: s, height: s }}>
      <Canvas style={{ flex: 1 }}>
        <Group>
          {glow && (
            <Path path={vPath} style="fill" opacity={0.25}>
              <LinearGradient start={vec(0, 0)} end={vec(s, s)} colors={['#10B981', '#059669']} />
            </Path>
          )}
          <Path path={vPath} style="fill">
            <LinearGradient start={vec(0, 0)} end={vec(s, s)} colors={['#0EA5E9', '#10B981']} />
          </Path>
          <Path path={circuit} style="stroke" strokeWidth={s * 0.018} color="#022C22" strokeCap="round" />
          <Circle cx={s * 0.32} cy={s * 0.30} r={s * 0.022} color="#ECFDF5" />
          <Circle cx={s * 0.68} cy={s * 0.30} r={s * 0.022} color="#ECFDF5" />
          <Circle cx={s * 0.50} cy={s * 0.62} r={s * 0.024} color="#022C22" />
          <Circle cx={s * 0.50} cy={s * 0.62} r={s * 0.012} color="#ECFDF5" />
        </Group>
      </Canvas>
    </View>
  );
};
