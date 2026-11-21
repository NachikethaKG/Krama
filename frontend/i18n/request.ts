import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { LOCALE_COOKIE, fromAcceptLanguage, isLocale } from "./config";
import { loadMessages } from "./messages";

/** next-intl without locale routing (L2): the picker's cookie, then the browser's Accept-Language, else English. */
export default getRequestConfig(async () => {
  const chosen = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(chosen) ? chosen : fromAcceptLanguage((await headers()).get("accept-language"));
  return { locale, messages: await loadMessages(locale) };
});
