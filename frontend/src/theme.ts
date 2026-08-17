export const theme = {
  color: {
    surface: '#050F14',
    surface2: '#0B1B24',
    surface3: '#122936',
    onSurface: '#F0FDFA',
    onSurface2: '#A3C2C2',
    onSurface3: '#82A7A6',
    brand: '#10B981',
    brand2: '#059669',
    brand3: '#064E3B',
    onBrand: '#022C22',
    success: '#10B981',
    warning: '#F59E0B',
    error: '#EF4444',
    info: '#0EA5E9',
    border: '#163342',
    borderStrong: '#204B5E',
  },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 },
  radius: { sm: 6, md: 12, lg: 20, pill: 999 },
  font: {
    display: 'System',
    text: 'System',
  },
  gradients: {
    brand: ['#064E3B', '#059669', '#10B981'] as const,
    hero: ['#050F14', '#0B1B24', '#064E3B'] as const,
    hero2: ['#0B1B24', '#0F3A45', '#10B981'] as const,
    danger: ['#450A0A', '#EF4444'] as const,
  },
};

export type Theme = typeof theme;
