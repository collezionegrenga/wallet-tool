import React from "react";
import { useTranslation } from "react-i18next";

const LangSwitcher: React.FC = () => {
  const { i18n, t } = useTranslation();
  return (
    <div className="flex gap-2">
      <button
        className={`px-3 py-1 rounded ${i18n.language === "it" ? "bg-blue-600 text-white" : "bg-gray-200"}`}
        onClick={() => i18n.changeLanguage("it")}
      >
        {t("lang_it")}
      </button>
      <button
        className={`px-3 py-1 rounded ${i18n.language === "en" ? "bg-blue-600 text-white" : "bg-gray-200"}`}
        onClick={() => i18n.changeLanguage("en")}
      >
        {t("lang_en")}
      </button>
    </div>
  );
};
export default LangSwitcher; 