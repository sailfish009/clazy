/*
   This file is part of the clazy static checker.

  Copyright (C) 2015 Klarälvdalens Datakonsult AB, a KDAB Group company, info@kdab.com
  Author: Sérgio Martins <sergio.martins@kdab.com>

  Copyright (C) 2015 Sergio Martins <smartins@kde.org>

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

#ifndef DETACHING_TEMPORARIES_H
#define DETACHING_TEMPORARIES_H

#include "checks/detachingbase.h"

/**
 * Finds places where you're calling non-const member functions on temporaries.
 *
 * For example getList().first(), which would detach if the container is shared.
 * See README-deatching-temporary for more information
 */
class DetachingTemporary : public DetachingBase
{
public:
    DetachingTemporary(const std::string &name, const clang::CompilerInstance &ci);
    void VisitStmt(clang::Stmt *stm) override;
private:
    bool isDetachingMethod(clang::CXXMethodDecl *method) const;
    std::map<std::string, std::vector<std::string>> m_writeMethodsByType;
};

#endif
