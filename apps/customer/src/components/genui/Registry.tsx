"use client";

import ProductList from "./ProductList";
import CartDrawer from "./CartDrawer";
import CartConfirmation from "./CartConfirmation";
import RecommendGrid from "./RecommendGrid";
import WeatherCard from "./WeatherCard";
import TryOnResult from "./TryOnResult";

export const REGISTRY: Record<string, React.ComponentType<any>> = {
  ProductList,
  CartDrawer,
  CartConfirmation,
  RecommendGrid,
  WeatherCard,
  TryOnResult,
};

export function renderGenUI(
  component: string,
  data: any,
  sessionId: string,
  onCartUpdate?: () => void,
  onSendMessage?: (msg: string) => void,
) {
  const Comp = REGISTRY[component];
  if (!Comp) return null;
  return <Comp data={data} sessionId={sessionId} onCartUpdate={onCartUpdate} onSendMessage={onSendMessage} />;
}
