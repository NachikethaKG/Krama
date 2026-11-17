export * from "./types.js";
export { computeLandscapeFraming, type FramingTransform } from "./framing/landscape.js";
export { computePortraitFraming } from "./framing/portrait.js";
export { buildTutorialChapters, formatFFMetadata } from "./metadata/chapters.js";
export { formatVttTimestamp, generateWebVTT } from "./metadata/webvtt.js";
export { IntroCard, type IntroCardProps } from "./compositions/IntroCard.js";
export { OutroCard, type OutroCardProps } from "./compositions/OutroCard.js";
export { CursorOverlay, type CursorOverlayProps } from "./compositions/CursorOverlay.js";
export { HighlightOverlay, type HighlightOverlayProps } from "./compositions/HighlightOverlay.js";
export { RippleOverlay, type RippleOverlayProps } from "./compositions/RippleOverlay.js";
export { CaptionsOverlay, type CaptionsOverlayProps } from "./compositions/CaptionsOverlay.js";
export { VideoScene, type VideoSceneProps } from "./compositions/VideoScene.js";
export {
  TutorialComposition,
  calculateTotalFrames,
} from "./compositions/TutorialComposition.js";
export { RemotionRoot } from "./compositions/Root.js";
export { renderTutorialVideo } from "./renderer/render.js";
