export interface AuthState {
  jwtToken: string | null
  role: 'manager' | 'employee' | null
  teamId: number | null
  teamName: string | null
  name: string | null
  email: string | null
}
export interface Emotion { id: number; name: string; emoji: string | null }
export interface EmojiRow { emotion_name: string; frequency: number }
export interface IntensityRow { emotion_name: string; avg_intensity: number }
export interface EmojiReport { emoji_distribution: EmojiRow[]; negative_emotion_ratio: number; alert: string | null }
export interface IntensityReport { average_intensity: IntensityRow[] }
export interface FeedbackMessage { id: number; content: string; created_at: string }
