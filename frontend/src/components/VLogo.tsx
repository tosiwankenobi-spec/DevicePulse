import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

interface Props {
  size?: number;
  glow?: boolean;
}

// Web-safe fallback (Skia doesn't render V logo on web preview)
export const VLogo: React.FC<Props> = ({ size = 120 }) => {
  if (Platform.OS === 'web') {
    return (
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        <LinearGradient
          colors={['#0EA5E9', '#10B981']}
          style={{ width: size * 0.9, height: size * 0.9, borderRadius: size * 0.2, alignItems: 'center', justifyContent: 'center' }}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <Text style={{ fontSize: size * 0.55, fontWeight: '900', color: '#022C22', letterSpacing: -2 }}>V</Text>
          <View style={{ position: 'absolute', top: size * 0.22, left: size * 0.25, width: 4, height: 4, borderRadius: 2, backgroundColor: '#ECFDF5' }} />
          <View style={{ position: 'absolute', top: size * 0.22, right: size * 0.25, width: 4, height: 4, borderRadius: 2, backgroundColor: '#ECFDF5' }} />
        </LinearGradient>
      </View>
    );
  }

  // Native (iOS / Android) — use Skia
  const NativeLogo = require('./VLogo.native').VLogo;
  return <NativeLogo size={size} />;
};
