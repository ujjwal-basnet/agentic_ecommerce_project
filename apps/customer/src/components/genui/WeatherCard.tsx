"use client";

import { Cloud, Droplets, Wind, Thermometer } from "lucide-react";

export default function WeatherCard({
  data,
}: {
  data: any;
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
}) {
  const location = data?.location || "Unknown";
  const temp = data?.temperature ?? "--";
  const feelsLike = data?.feels_like ?? "--";
  const weather = data?.weather || "N/A";
  const humidity = data?.humidity ?? "--";
  const windSpeed = data?.wind_speed ?? "--";

  return (
    <div className="bg-surface-container-lowest rounded-2xl overflow-hidden shadow-sm border border-outline-variant/10 max-w-md">
      <div className="bg-gradient-to-br from-primary to-primary-dim p-6 text-on-primary">
        <div className="flex items-start justify-between">
          <div>
            <p className="font-label text-[10px] uppercase tracking-widest opacity-70">{location}</p>
            <p className="font-headline text-4xl font-light mt-2">{temp}°C</p>
            <p className="font-headline text-sm font-medium mt-1 opacity-90">{weather}</p>
          </div>
          <Cloud size={48} className="opacity-60" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4 p-5">
        <div>
          <div className="flex items-center gap-1.5 text-on-surface-variant mb-1">
            <Thermometer size={13} />
            <span className="font-label text-[9px] uppercase tracking-widest">Feels like</span>
          </div>
          <p className="font-headline text-sm font-semibold text-on-surface">{feelsLike}°C</p>
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-on-surface-variant mb-1">
            <Droplets size={13} />
            <span className="font-label text-[9px] uppercase tracking-widest">Humidity</span>
          </div>
          <p className="font-headline text-sm font-semibold text-on-surface">{humidity}%</p>
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-on-surface-variant mb-1">
            <Wind size={13} />
            <span className="font-label text-[9px] uppercase tracking-widest">Wind</span>
          </div>
          <p className="font-headline text-sm font-semibold text-on-surface">{windSpeed} m/s</p>
        </div>
      </div>
    </div>
  );
}
