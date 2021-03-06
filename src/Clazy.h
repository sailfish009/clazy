/*
   This file is part of the clazy static checker.

  Copyright (C) 2015 Klarälvdalens Datakonsult AB, a KDAB Group company, info@kdab.com
  Author: Sérgio Martins <sergio.martins@kdab.com>

  Copyright (C) 2015-2016 Sergio Martins <smartins@kde.org>

  This library is free software; you can redistribute it and/or
  modify it under the terms of the GNU Library General Public
  License as published by the Free Software Foundation; either
  version 2 of the License, or (at your option) any later version.

  This library is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Library General Public License for more details.

  You should have received a copy of the GNU Library General Public License
  along with this library; see the file COPYING.LIB.  If not, write to
  the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
  Boston, MA 02110-1301, USA.
*/

#ifndef CLAZY_AST_ACTION_H
#define CLAZY_AST_ACTION_H

#include "checkmanager.h"

#include <clang/AST/ASTConsumer.h>
#include <clang/Frontend/FrontendAction.h>
#include <memory>
#include <vector>
#include <string>

namespace clang {
    class CompilerInstance;
}

class CheckManager;

class ClazyASTAction : public clang::PluginASTAction
{
public:
    ClazyASTAction();

protected:
    std::unique_ptr<clang::ASTConsumer> CreateASTConsumer(clang::CompilerInstance &ci, llvm::StringRef) override;
    bool ParseArgs(const clang::CompilerInstance &ci, const std::vector<std::string> &args_) override;
    void PrintHelp(llvm::raw_ostream &ros);
private:
    RegisteredCheck::List m_checks;
    bool m_inplaceFixits = true;
    CheckManager *const m_checkManager;
};

#endif
