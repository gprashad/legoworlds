interface GreenLightButtonProps {
  onClick: () => void
  disabled: boolean
}

export function GreenLightButton({ onClick, disabled }: GreenLightButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full py-4 rounded-xl text-lg font-bold bg-greenlight text-white hover:bg-greenlight-hover active:scale-[0.98] transition-all shadow-lg shadow-greenlight/30 disabled:opacity-40 disabled:cursor-not-allowed"
    >
      🟢 GREEN LIGHT — START PRODUCTION!
    </button>
  )
}
