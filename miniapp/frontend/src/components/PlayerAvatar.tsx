interface PlayerAvatarProps {
  name?: string;
  photoUrl?: string;
  size?: 'sm' | 'md' | 'lg';
  rank?: number;
  className?: string;
}

const sizeClasses = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-12 h-12 text-sm',
  lg: 'w-16 h-16 text-lg',
};

const rankColors: Record<number, string> = {
  1: 'bg-yellow-400 text-yellow-900',
  2: 'bg-gray-300 text-gray-700',
  3: 'bg-orange-400 text-orange-900',
};

export default function PlayerAvatar({
  name = '?',
  photoUrl,
  size = 'md',
  rank,
  className = '',
}: PlayerAvatarProps) {
  const initials = name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className={`relative inline-flex ${className}`}>
      {photoUrl ? (
        <img
          src={photoUrl}
          alt={name}
          className={`${sizeClasses[size]} rounded-full object-cover`}
        />
      ) : (
        <div
          className={`${sizeClasses[size]} rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white font-semibold`}
        >
          {initials || '?'}
        </div>
      )}
      {rank && rank <= 3 && (
        <span
          className={`absolute -bottom-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
            rankColors[rank] || 'bg-gray-200 text-gray-600'
          }`}
        >
          {rank}
        </span>
      )}
    </div>
  );
}
