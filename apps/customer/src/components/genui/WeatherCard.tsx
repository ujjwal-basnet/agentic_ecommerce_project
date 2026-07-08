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
    <div className="bg-white rounded-2xl overflow-hidden shadow-card max-w-sm">
      <div className="bg-[#1d1d1f] p-5 text-white">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider opacity-60 font-label">{location}</p>
            <p className="font-headline text-[36px] font-light mt-1 leading-tight">{temp}°C</p>
            <p className="font-headline text-[13px] font-medium mt-0.5 opacity-80">{weather}</p>
          </div>
          <Cloud size={40} className="opacity-40" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3 p-4">
        <div>
          <div className="flex items-center gap-1 text-[#86868b] mb-0.5">
            <Thermometer size={11} />
            <span className="text-[9px] uppercase tracking-wider font-label">Feels like</span>
          </div>
          <p className="font-headline text-[13px] font-semibold text-[#1d1d1f]">{feelsLike}°C</p>
        </div>
        <div>
          <div className="flex items-center gap-1 text-[#86868b] mb-0.5">
            <Droplets size={11} />
            <span className="text-[9px] uppercase tracking-wider font-label">Humidity</span>
          </div>
          <p className="font-headline text-[13px] font-semibold text-[#1d1d1f]">{humidity}%</p>
        </div>
        <div>
          <div className="flex items-center gap-1 text-[#86868b] mb-0.5">
            <Wind size={11} />
            <span className="text-[9px] uppercase tracking-wider font-label">Wind</span>
          </div>
          <p className="font-headline text-[13px] font-semibold text-[#1d1d1f]">{windSpeed} m/s</p>
        </div>
      </div>
    </div>
  );
}
